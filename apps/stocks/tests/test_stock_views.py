from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.stocks.models import Interest, NewsItem, Price, Stock
from apps.watchlist.models import Watchlist, WatchlistItem


class StockViewsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.stock = Stock.objects.create(
            symbol="VIEW1",
            name="View One",
            market=Stock.Market.USA,
            sector="Tech",
            is_active=True,
        )
        Stock.objects.create(
            symbol="VIEW2",
            name="Another Stock",
            market=Stock.Market.KOREA,
            sector="Finance",
            is_active=True,
        )

    def test_stock_list_search_filters_symbol_and_name(self):
        response = self.client.get(reverse("stocks:list"), {"q": "VIEW1"})

        self.assertEqual(response.status_code, 200)
        stocks = list(response.context["stocks"])
        self.assertEqual(len(stocks), 1)
        self.assertEqual(stocks[0].symbol, "VIEW1")

    def test_stock_detail_renders_chart_and_watchlist_context(self):
        today = timezone.localdate()
        Price.objects.create(
            stock=self.stock,
            traded_at=today - timedelta(days=1),
            open_price=Decimal("95"),
            high_price=Decimal("101"),
            low_price=Decimal("94"),
            close_price=Decimal("100"),
            volume=1000,
        )
        Price.objects.create(
            stock=self.stock,
            traded_at=today,
            open_price=Decimal("101"),
            high_price=Decimal("106"),
            low_price=Decimal("98"),
            close_price=Decimal("104"),
            volume=1200,
        )
        now = timezone.now()
        Interest.objects.create(
            stock=self.stock,
            source=Interest.Source.REDDIT,
            recorded_at=now - timedelta(hours=2),
            mentions=8,
            metadata={"samples": [{"title": "View One momentum"}]},
        )
        Interest.objects.create(
            stock=self.stock,
            source=Interest.Source.NEWS,
            recorded_at=now - timedelta(hours=1),
            mentions=6,
            metadata={"samples": [{"title": "View One guidance"}]},
        )
        NewsItem.objects.create(
            stock=self.stock,
            title="View One expands globally",
            url="https://example.com/view1-news",
            publisher="Example",
            published_at=now,
        )

        user = get_user_model().objects.create_user(
            username="viewer",
            email="viewer@example.com",
            password="pass1234",
        )
        watchlist = Watchlist.objects.create(user=user, name="My List", is_default=True)
        WatchlistItem.objects.create(watchlist=watchlist, stock=self.stock)
        self.client.force_login(user)

        response = self.client.get(reverse("stocks:detail", kwargs={"symbol": self.stock.symbol}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["price_chart_data"]), 2)
        self.assertGreaterEqual(len(response.context["interest_chart_data"]), 1)
        self.assertGreaterEqual(len(response.context["news_items"]), 1)
        self.assertEqual(len(response.context["watchlists"]), 1)
        self.assertIn(watchlist.id, response.context["watchlist_ids_with_stock"])

    @patch("apps.stocks.views.get_stock_interest_anomaly", return_value={})
    @patch("apps.stocks.views.build_stock_topic_cloud", return_value=[])
    @patch("apps.stocks.views.get_related_news", return_value=[])
    def test_stock_detail_uses_cache_for_expensive_service_calls(
        self,
        mock_related_news,
        mock_topic_cloud,
        mock_stock_anomaly,
    ):
        now = timezone.now()
        Price.objects.create(
            stock=self.stock,
            traded_at=timezone.localdate(),
            open_price=Decimal("100"),
            high_price=Decimal("105"),
            low_price=Decimal("99"),
            close_price=Decimal("104"),
            volume=1000,
        )
        Interest.objects.create(
            stock=self.stock,
            source=Interest.Source.REDDIT,
            recorded_at=now,
            mentions=4,
            metadata={"samples": [{"title": "View One signal"}]},
        )

        url = reverse("stocks:detail", kwargs={"symbol": self.stock.symbol})
        first = self.client.get(url)
        second = self.client.get(url)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        mock_related_news.assert_called_once()
        mock_topic_cloud.assert_called_once()
        mock_stock_anomaly.assert_called_once()
