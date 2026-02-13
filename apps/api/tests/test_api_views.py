from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import Subscription
from apps.stocks.models import Interest, NewsItem, Price, Stock
from services.stock_service import ensure_index_stocks


class ApiViewsTests(APITestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.pro_user = User.objects.create_user(
            username="api-pro",
            email="api-pro@example.com",
            password="pass1234",
        )
        Subscription.objects.create(
            user=self.pro_user,
            plan=Subscription.Plan.PRO,
            is_active=True,
            start_date=timezone.localdate() - timedelta(days=1),
            end_date=timezone.localdate() + timedelta(days=30),
        )
        self.free_user = User.objects.create_user(
            username="api-free",
            email="api-free@example.com",
            password="pass1234",
        )
        Subscription.objects.create(
            user=self.free_user,
            plan=Subscription.Plan.FREE,
            is_active=True,
            start_date=timezone.localdate() - timedelta(days=1),
            end_date=timezone.localdate() + timedelta(days=30),
        )

        self.stock = Stock.objects.create(
            symbol="API1",
            name="API One",
            market=Stock.Market.USA,
            sector="Tech",
            is_active=True,
        )
        self.other = Stock.objects.create(
            symbol="API2",
            name="API Two",
            market=Stock.Market.KOREA,
            sector="Finance",
            is_active=True,
        )

        today = timezone.localdate()
        Price.objects.create(
            stock=self.stock,
            traded_at=today - timedelta(days=1),
            open_price=Decimal("95"),
            high_price=Decimal("100"),
            low_price=Decimal("93"),
            close_price=Decimal("99"),
            volume=1200,
        )
        Price.objects.create(
            stock=self.stock,
            traded_at=today,
            open_price=Decimal("100"),
            high_price=Decimal("106"),
            low_price=Decimal("98"),
            close_price=Decimal("103"),
            volume=1500,
        )

        now = timezone.now()
        Interest.objects.create(
            stock=self.stock,
            source=Interest.Source.REDDIT,
            recorded_at=now - timedelta(hours=2),
            mentions=12,
            metadata={"samples": [{"title": "API1 momentum"}]},
        )
        Interest.objects.create(
            stock=self.other,
            source=Interest.Source.REDDIT,
            recorded_at=now - timedelta(hours=2),
            mentions=3,
            metadata={"samples": [{"title": "API2 mention"}]},
        )
        NewsItem.objects.create(
            stock=self.stock,
            title="API One launches product",
            url="https://example.com/api1-news",
            publisher="Example",
            published_at=now,
        )

    def _auth_pro_user(self):
        self.client.force_authenticate(user=self.pro_user)

    def _seed_anomaly_history(self):
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

    def test_market_summary_api_returns_success_shape(self):
        self._auth_pro_user()
        ensure_index_stocks()

        response = self.client.get(reverse("api:market-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(len(response.data["data"]), 4)
        self.assertIn("label", response.data["data"][0])
        self.assertIn("price", response.data["data"][0])
        self.assertIn("change_rate", response.data["data"][0])

    def test_top_interest_api_returns_ranked_rows(self):
        self._auth_pro_user()
        response = self.client.get(reverse("api:top-interest"), {"limit": 1, "hours": 24})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertIn("meta", response.data)
        self.assertIn("pagination", response.data["meta"])
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["symbol"], "API1")
        self.assertEqual(response.data["data"][0]["total_mentions"], 12)

    def test_interest_anomaly_api_returns_detected_symbol(self):
        self._auth_pro_user()
        self._seed_anomaly_history()

        response = self.client.get(
            reverse("api:interest-anomalies"),
            {"limit": 5, "recent_hours": 6, "baseline_hours": 72},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertIn("meta", response.data)
        self.assertIn("pagination", response.data["meta"])
        symbols = [row["symbol"] for row in response.data["data"]]
        self.assertIn("API1", symbols)

    def test_stock_summary_api_returns_price_interest_and_news(self):
        self._auth_pro_user()
        response = self.client.get(
            reverse("api:stock-summary", kwargs={"symbol": "api1"}),
            {"price_days": 30, "interest_days": 60, "news_limit": 5},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        payload = response.data["data"]
        self.assertEqual(payload["stock"]["symbol"], "API1")
        self.assertIsNotNone(payload["latest_price"])
        self.assertEqual(payload["latest_price"]["close_price"], 103.0)
        self.assertGreaterEqual(len(payload["price_chart_data"]), 2)
        self.assertGreaterEqual(len(payload["interest_chart_data"]), 1)
        self.assertGreaterEqual(len(payload["news_items"]), 1)

    def test_top_interest_api_returns_400_for_invalid_limit(self):
        self._auth_pro_user()
        response = self.client.get(reverse("api:top-interest"), {"limit": 0})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertIn("limit", response.data["errors"])

    def test_stock_summary_api_returns_404_for_unknown_symbol(self):
        self._auth_pro_user()
        response = self.client.get(reverse("api:stock-summary", kwargs={"symbol": "NOPE"}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(response.data["code"], "NOT_FOUND")

    def test_market_summary_api_requires_authentication(self):
        response = self.client.get(reverse("api:market-summary"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(response.data["code"], "FORBIDDEN")

    def test_market_summary_api_denies_free_plan_user(self):
        self.client.force_authenticate(user=self.free_user)

        response = self.client.get(reverse("api:market-summary"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(response.data["code"], "FORBIDDEN")

    def test_market_summary_api_returns_429_when_throttle_exceeded(self):
        self._auth_pro_user()
        url = reverse("api:market-summary")

        with patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"api_read": "2/min"}):
            first = self.client.get(url)
            second = self.client.get(url)
            third = self.client.get(url)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(third.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(third.data["status"], "error")
        self.assertEqual(third.data["code"], "RATE_LIMITED")

    def test_top_interest_api_supports_pagination_params(self):
        self._auth_pro_user()
        response = self.client.get(
            reverse("api:top-interest"),
            {"limit": 2, "hours": 24, "page": 2, "page_size": 1},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["symbol"], "API2")
        pagination = response.data["meta"]["pagination"]
        self.assertEqual(pagination["page"], 2)
        self.assertEqual(pagination["page_size"], 1)
        self.assertEqual(pagination["total_items"], 2)
