from decimal import Decimal
from unittest.mock import patch

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

    def test_market_summary_partial_only_calls_market_service(self):
        with (
            patch(
                "apps.dashboard.views.get_market_summary",
                return_value=[{"label": "KOSPI", "price": "1.00", "change_rate": 0.0}],
            ) as mock_market,
            patch("apps.dashboard.views.get_top_interest_stocks") as mock_top,
            patch("apps.dashboard.views.get_sector_interest_heatmap") as mock_heatmap,
            patch("apps.dashboard.views.get_interest_timeline") as mock_timeline,
            patch("apps.dashboard.views.detect_interest_anomalies") as mock_anomaly,
        ):
            response = self.client.get(reverse("dashboard:market-summary-partial"))

        self.assertEqual(response.status_code, 200)
        mock_market.assert_called_once()
        mock_top.assert_not_called()
        mock_heatmap.assert_not_called()
        mock_timeline.assert_not_called()
        mock_anomaly.assert_not_called()

    def test_top_interest_partial_only_calls_interest_service(self):
        with (
            patch("apps.dashboard.views.get_market_summary") as mock_market,
            patch("apps.dashboard.views.get_top_interest_stocks", return_value=[]) as mock_top,
            patch("apps.dashboard.views.get_sector_interest_heatmap") as mock_heatmap,
            patch("apps.dashboard.views.get_interest_timeline") as mock_timeline,
            patch("apps.dashboard.views.detect_interest_anomalies") as mock_anomaly,
        ):
            response = self.client.get(reverse("dashboard:top-interest-partial"))

        self.assertEqual(response.status_code, 200)
        mock_market.assert_not_called()
        mock_top.assert_called_once()
        mock_heatmap.assert_not_called()
        mock_timeline.assert_not_called()
        mock_anomaly.assert_not_called()

    def test_heatmap_partial_only_calls_heatmap_service(self):
        with (
            patch("apps.dashboard.views.get_market_summary") as mock_market,
            patch("apps.dashboard.views.get_top_interest_stocks") as mock_top,
            patch("apps.dashboard.views.get_sector_interest_heatmap", return_value=[]) as mock_heatmap,
            patch("apps.dashboard.views.get_interest_timeline") as mock_timeline,
            patch("apps.dashboard.views.detect_interest_anomalies") as mock_anomaly,
        ):
            response = self.client.get(reverse("dashboard:interest-heatmap-partial"))

        self.assertEqual(response.status_code, 200)
        mock_market.assert_not_called()
        mock_top.assert_not_called()
        mock_heatmap.assert_called_once()
        mock_timeline.assert_not_called()
        mock_anomaly.assert_not_called()

    def test_timeline_partial_only_calls_timeline_service(self):
        with (
            patch("apps.dashboard.views.get_market_summary") as mock_market,
            patch("apps.dashboard.views.get_top_interest_stocks") as mock_top,
            patch("apps.dashboard.views.get_sector_interest_heatmap") as mock_heatmap,
            patch("apps.dashboard.views.get_interest_timeline", return_value=[]) as mock_timeline,
            patch("apps.dashboard.views.detect_interest_anomalies") as mock_anomaly,
        ):
            response = self.client.get(reverse("dashboard:interest-timeline-partial"))

        self.assertEqual(response.status_code, 200)
        mock_market.assert_not_called()
        mock_top.assert_not_called()
        mock_heatmap.assert_not_called()
        mock_timeline.assert_called_once()
        mock_anomaly.assert_not_called()

    def test_anomaly_partial_only_calls_anomaly_service(self):
        with (
            patch("apps.dashboard.views.get_market_summary") as mock_market,
            patch("apps.dashboard.views.get_top_interest_stocks") as mock_top,
            patch("apps.dashboard.views.get_sector_interest_heatmap") as mock_heatmap,
            patch("apps.dashboard.views.get_interest_timeline") as mock_timeline,
            patch("apps.dashboard.views.detect_interest_anomalies", return_value=[]) as mock_anomaly,
        ):
            response = self.client.get(reverse("dashboard:anomaly-alert-partial"))

        self.assertEqual(response.status_code, 200)
        mock_market.assert_not_called()
        mock_top.assert_not_called()
        mock_heatmap.assert_not_called()
        mock_timeline.assert_not_called()
        mock_anomaly.assert_called_once()
