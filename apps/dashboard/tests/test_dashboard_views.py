from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.stocks.models import Interest, Price, Stock


class DashboardViewsTests(TestCase):
    def setUp(self):
        self.stock = Stock.objects.create(
            symbol="KOSPI",
            name="KOSPI Index",
            market=Stock.Market.KOREA,
            sector="INDEX",
            is_active=True,
        )
        Price.objects.create(
            stock=self.stock,
            traded_at=timezone.localdate(),
            open_price=Decimal("100"),
            high_price=Decimal("103"),
            low_price=Decimal("98"),
            close_price=Decimal("102"),
            volume=1000,
        )
        bucket_now = timezone.now().replace(minute=0, second=0, microsecond=0)
        Interest.objects.create(
            stock=self.stock,
            source=Interest.Source.REDDIT,
            recorded_at=bucket_now,
            mentions=12,
        )

    def test_dashboard_home_renders_with_context_flags(self):
        response = self.client.get(reverse("dashboard:home"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["has_market_data"])
        self.assertTrue(response.context["has_interest_data"])
        self.assertTrue(response.context["has_heatmap_data"])
        self.assertTrue(response.context["has_timeline_data"])
        self.assertIn("has_anomaly_data", response.context)

    def test_dashboard_partials_return_200(self):
        partials = {
            "dashboard:market-summary-partial": "dashboard/_market_summary_panel.html",
            "dashboard:top-interest-partial": "dashboard/_top_interest_panel.html",
            "dashboard:interest-heatmap-partial": "dashboard/_interest_heatmap_panel.html",
            "dashboard:interest-timeline-partial": "dashboard/_interest_timeline_panel.html",
            "dashboard:anomaly-alert-partial": "dashboard/_anomaly_alert_panel.html",
        }

        for name, template_name in partials.items():
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template_name)
