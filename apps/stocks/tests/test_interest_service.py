from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.stocks.models import Interest, NewsItem, Stock
from services.interest_service import (
    collect_interest_snapshot,
    detect_interest_anomalies,
    get_top_interest_stocks,
)


class InterestServiceTests(TestCase):
    def setUp(self):
        self.stock = Stock.objects.create(
            symbol="ANOM",
            name="Anomaly Inc",
            market=Stock.Market.USA,
            sector="Tech",
            is_active=True,
        )

    def test_collect_interest_snapshot_merges_crawler_and_news_mentions(self):
        now = timezone.now()
        NewsItem.objects.create(
            stock=self.stock,
            title="Anomaly earnings beat",
            url="https://example.com/news/anom-1",
            publisher="Example",
            published_at=now,
        )

        class FakeCrawler:
            source = Interest.Source.REDDIT

            def fetch(self, stocks, limit_per_symbol=3):
                symbol = stocks[0].symbol
                return [
                    SimpleNamespace(
                        symbol=symbol,
                        source=Interest.Source.REDDIT,
                        title="ANOM to the moon",
                        url="https://reddit.example.com/1",
                        published_at=now,
                    ),
                    SimpleNamespace(
                        symbol=symbol,
                        source=Interest.Source.REDDIT,
                        title="ANOM update",
                        url="https://reddit.example.com/2",
                        published_at=now,
                    ),
                ]

        with patch("services.interest_service.DEFAULT_SOURCE_CRAWLERS", (FakeCrawler,)):
            result = collect_interest_snapshot(limit_stocks=5, limit_per_symbol=3)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["inserted"], 2)
        self.assertEqual(result["sources"][Interest.Source.REDDIT], 2)
        self.assertEqual(result["sources"][Interest.Source.NEWS], 1)

        records = Interest.objects.filter(stock=self.stock).order_by("source")
        self.assertEqual(records.count(), 2)
        reddit_record = records.get(source=Interest.Source.REDDIT)
        self.assertEqual(reddit_record.mentions, 2)
        self.assertEqual(len(reddit_record.metadata.get("samples", [])), 2)

    def test_detect_interest_anomalies_finds_surge(self):
        now = timezone.now().replace(minute=0, second=0, microsecond=0)

        for hours_ago in range(6, 78):
            Interest.objects.create(
                stock=self.stock,
                source=Interest.Source.REDDIT,
                recorded_at=now - timedelta(hours=hours_ago),
                mentions=1,
            )
        for hours_ago in range(0, 6):
            Interest.objects.create(
                stock=self.stock,
                source=Interest.Source.REDDIT,
                recorded_at=now - timedelta(hours=hours_ago),
                mentions=12,
            )

        anomalies = detect_interest_anomalies(limit=5)

        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["symbol"], "ANOM")
        self.assertEqual(anomalies[0]["severity"], "high")
        self.assertGreaterEqual(anomalies[0]["surge_ratio"], 4.0)

    def test_get_top_interest_stocks_only_positive_filters_zero_mentions(self):
        positive = self.stock
        negative = Stock.objects.create(
            symbol="ZERO",
            name="Zero Corp",
            market=Stock.Market.USA,
            sector="Tech",
            is_active=True,
        )
        Interest.objects.create(
            stock=positive,
            source=Interest.Source.NAVER,
            recorded_at=timezone.now(),
            mentions=5,
        )
        Interest.objects.create(
            stock=negative,
            source=Interest.Source.NAVER,
            recorded_at=timezone.now() - timedelta(hours=30),
            mentions=50,
        )

        rows = get_top_interest_stocks(limit=10, hours=24, only_positive=True)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].symbol, positive.symbol)

    def test_detect_interest_anomalies_query_count_is_bounded(self):
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        extra_stocks = [
            Stock.objects.create(
                symbol=f"AN{idx}",
                name=f"Anomaly {idx}",
                market=Stock.Market.USA,
                sector="Tech",
                is_active=True,
            )
            for idx in range(3)
        ]
        for stock in [self.stock, *extra_stocks]:
            for hours_ago in range(6, 78):
                Interest.objects.create(
                    stock=stock,
                    source=Interest.Source.REDDIT,
                    recorded_at=now - timedelta(hours=hours_ago),
                    mentions=1,
                )
            for hours_ago in range(0, 6):
                Interest.objects.create(
                    stock=stock,
                    source=Interest.Source.REDDIT,
                    recorded_at=now - timedelta(hours=hours_ago),
                    mentions=10,
                )

        with self.assertNumQueries(2):
            anomalies = detect_interest_anomalies(limit=10)

        self.assertGreaterEqual(len(anomalies), 1)

    def test_collect_interest_snapshot_news_query_count_is_bounded(self):
        now = timezone.now()
        for idx in range(30):
            NewsItem.objects.create(
                stock=self.stock,
                title=f"News {idx}",
                url=f"https://example.com/news/{idx}",
                publisher="Example",
                published_at=now - timedelta(minutes=idx),
            )

        class EmptyCrawler:
            source = Interest.Source.REDDIT

            def fetch(self, stocks, limit_per_symbol=3):
                return []

        with patch("services.interest_service.DEFAULT_SOURCE_CRAWLERS", (EmptyCrawler,)):
            with CaptureQueriesContext(connection) as queries:
                result = collect_interest_snapshot(limit_stocks=5, limit_per_symbol=3)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["sources"][Interest.Source.REDDIT], 0)
        self.assertEqual(result["sources"][Interest.Source.NEWS], 30)
        self.assertLessEqual(len(queries), 10)
