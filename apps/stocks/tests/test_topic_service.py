from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.stocks.models import Interest, NewsItem, Stock
from services.topic_service import _collect_text_samples, build_stock_topic_cloud


class TopicServiceTests(TestCase):
    def setUp(self):
        self.stock = Stock.objects.create(
            symbol="ACME",
            name="Acme Holdings",
            market=Stock.Market.USA,
            sector="Tech",
            is_active=True,
        )

    def test_build_stock_topic_cloud_returns_empty_without_samples(self):
        cloud = build_stock_topic_cloud(stock=self.stock, hours=72, max_keywords=10)

        self.assertEqual(cloud, [])

    def test_build_stock_topic_cloud_filters_stopwords_and_stock_tokens(self):
        NewsItem.objects.create(
            stock=self.stock,
            title="ACME stock market breakout breakout holdings",
            url="https://example.com/topic-filter",
            publisher="Example",
            published_at=timezone.now(),
        )

        cloud = build_stock_topic_cloud(stock=self.stock, hours=72, max_keywords=10)

        self.assertEqual(len(cloud), 1)
        self.assertEqual(cloud[0]["keyword"], "breakout")
        self.assertEqual(cloud[0]["count"], 2)
        self.assertEqual(cloud[0]["weight"], 1.0)
        self.assertEqual(cloud[0]["font_size"], 1.6)

    def test_build_stock_topic_cloud_respects_max_keywords_and_weights(self):
        now = timezone.now()
        NewsItem.objects.create(
            stock=self.stock,
            title="alpha alpha beta",
            url="https://example.com/topic-1",
            publisher="Example",
            published_at=now,
        )
        NewsItem.objects.create(
            stock=self.stock,
            title="alpha gamma",
            url="https://example.com/topic-2",
            publisher="Example",
            published_at=now - timedelta(minutes=1),
        )
        Interest.objects.create(
            stock=self.stock,
            source=Interest.Source.REDDIT,
            recorded_at=now,
            mentions=4,
            metadata={"samples": [{"title": "beta delta"}]},
        )

        cloud = build_stock_topic_cloud(stock=self.stock, hours=72, max_keywords=2)

        self.assertEqual(len(cloud), 2)
        self.assertEqual(cloud[0]["keyword"], "alpha")
        self.assertEqual(cloud[0]["count"], 3)
        self.assertEqual(cloud[0]["weight"], 1.0)
        self.assertEqual(cloud[0]["font_size"], 1.6)
        self.assertEqual(cloud[1]["keyword"], "beta")
        self.assertEqual(cloud[1]["count"], 2)
        self.assertEqual(cloud[1]["weight"], 0.6667)
        self.assertEqual(cloud[1]["font_size"], 1.353)

    def test_collect_text_samples_respects_time_window_and_max_size(self):
        now = timezone.now()

        for idx in range(130):
            NewsItem.objects.create(
                stock=self.stock,
                title=f"recent-news-{idx}",
                url=f"https://example.com/recent-news-{idx}",
                publisher="Example",
                published_at=now - timedelta(minutes=idx),
            )

        old_news = NewsItem.objects.create(
            stock=self.stock,
            title="too-old-news",
            url="https://example.com/too-old-news",
            publisher="Example",
            published_at=now - timedelta(hours=30),
        )
        NewsItem.objects.filter(pk=old_news.pk).update(created_at=now - timedelta(hours=30))

        for idx in range(90):
            Interest.objects.create(
                stock=self.stock,
                source=Interest.Source.NEWS,
                recorded_at=now - timedelta(minutes=idx),
                mentions=1,
                metadata={"samples": [{"title": f"recent-interest-{idx}"}]},
            )

        Interest.objects.create(
            stock=self.stock,
            source=Interest.Source.REDDIT,
            recorded_at=now - timedelta(hours=30),
            mentions=1,
            metadata={"samples": [{"title": "too-old-interest"}]},
        )

        samples = _collect_text_samples(stock=self.stock, hours=24)

        self.assertEqual(len(samples), 200)
        self.assertNotIn("too-old-news", samples)
        self.assertNotIn("too-old-interest", samples)
