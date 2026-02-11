from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.stocks.models import NewsItem, Stock
from services.news_service import collect_news_items, get_latest_news_for_symbols


class NewsServiceTests(TestCase):
    def setUp(self):
        self.stock = Stock.objects.create(
            symbol="NEWS1",
            name="News Corp",
            market=Stock.Market.USA,
            sector="Media",
            is_active=True,
        )

    def test_collect_news_items_returns_error_when_no_active_stock(self):
        Stock.objects.all().delete()

        result = collect_news_items(limit_stocks=3, limit_per_symbol=2)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "NO_STOCKS")

    def test_collect_news_items_upserts_by_stock_and_url(self):
        now = timezone.now()

        class FakeCrawler:
            source = NewsItem.Source.NEWS

            def fetch(self, stocks, limit_per_symbol=3):
                symbol = stocks[0].symbol
                return [
                    SimpleNamespace(
                        symbol=symbol,
                        source=NewsItem.Source.NEWS,
                        title="Initial headline",
                        url="https://example.com/news/dup",
                        published_at=now,
                        metadata={"publisher": "One"},
                    ),
                    SimpleNamespace(
                        symbol=symbol,
                        source=NewsItem.Source.NEWS,
                        title="Updated headline",
                        url="https://example.com/news/dup",
                        published_at=now,
                        metadata={"publisher": "Two"},
                    ),
                ]

        with patch("services.news_service.NewsCrawler", return_value=FakeCrawler()):
            result = collect_news_items(limit_stocks=3, limit_per_symbol=2)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(NewsItem.objects.count(), 1)
        item = NewsItem.objects.get(stock=self.stock)
        self.assertEqual(item.title, "Updated headline")
        self.assertEqual(item.publisher, "Two")

    def test_get_latest_news_for_symbols_filters_by_created_at(self):
        now = timezone.now()
        recent = NewsItem.objects.create(
            stock=self.stock,
            title="Recent headline",
            url="https://example.com/news/recent",
            publisher="RecentPub",
            published_at=now,
        )
        old = NewsItem.objects.create(
            stock=self.stock,
            title="Old headline",
            url="https://example.com/news/old",
            publisher="OldPub",
            published_at=now - timedelta(days=3),
        )
        NewsItem.objects.filter(id=old.id).update(created_at=now - timedelta(days=3))
        NewsItem.objects.filter(id=recent.id).update(created_at=now)

        rows = get_latest_news_for_symbols([self.stock.symbol], limit_per_symbol=5, since_hours=24)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Recent headline")
