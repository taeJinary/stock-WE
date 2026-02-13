from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
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

    def test_get_latest_news_for_symbols_uses_bounded_queries_for_multiple_symbols(self):
        second_stock = Stock.objects.create(
            symbol="NEWS2",
            name="News Two",
            market=Stock.Market.USA,
            sector="Media",
            is_active=True,
        )
        third_stock = Stock.objects.create(
            symbol="NEWS3",
            name="News Three",
            market=Stock.Market.KOREA,
            sector="Media",
            is_active=True,
        )
        now = timezone.now()

        for idx in range(4):
            NewsItem.objects.create(
                stock=self.stock,
                title=f"NEWS1-{idx}",
                url=f"https://example.com/news1/{idx}",
                publisher="P1",
                published_at=now - timedelta(minutes=idx),
            )
            NewsItem.objects.create(
                stock=second_stock,
                title=f"NEWS2-{idx}",
                url=f"https://example.com/news2/{idx}",
                publisher="P2",
                published_at=now - timedelta(minutes=idx),
            )
            NewsItem.objects.create(
                stock=third_stock,
                title=f"NEWS3-{idx}",
                url=f"https://example.com/news3/{idx}",
                publisher="P3",
                published_at=now - timedelta(minutes=idx),
            )

        symbols = [self.stock.symbol, second_stock.symbol, third_stock.symbol]
        with CaptureQueriesContext(connection) as queries:
            rows = get_latest_news_for_symbols(symbols, limit_per_symbol=2, since_hours=24)

        self.assertEqual(len(rows), 6)
        self.assertLessEqual(len(queries), 2)
        by_symbol = {}
        for row in rows:
            by_symbol.setdefault(row["symbol"], []).append(row["title"])

        self.assertEqual(by_symbol[self.stock.symbol], ["NEWS1-0", "NEWS1-1"])
        self.assertEqual(by_symbol[second_stock.symbol], ["NEWS2-0", "NEWS2-1"])
        self.assertEqual(by_symbol[third_stock.symbol], ["NEWS3-0", "NEWS3-1"])
