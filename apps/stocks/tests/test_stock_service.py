from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.stocks.models import Price, Stock
from services.stock_service import (
    INDEX_DEFINITIONS,
    ensure_index_stocks,
    get_market_summary,
    refresh_market_prices,
)


class StockServiceTests(TestCase):
    def test_ensure_index_stocks_creates_expected_defaults(self):
        result = ensure_index_stocks()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["created"], len(INDEX_DEFINITIONS))
        self.assertEqual(Stock.objects.count(), len(INDEX_DEFINITIONS))

    @patch("services.stock_service.time.sleep")
    @patch("services.stock_service.fetch_alpha_vantage_quote")
    def test_refresh_market_prices_handles_rate_limit_and_skips_remaining(
        self,
        mock_fetch_alpha_vantage_quote,
        _mock_sleep,
    ):
        ensure_index_stocks()
        today = timezone.localdate()
        mock_fetch_alpha_vantage_quote.side_effect = [
            {
                "status": "success",
                "data": {
                    "open_price": Decimal("100"),
                    "high_price": Decimal("110"),
                    "low_price": Decimal("90"),
                    "close_price": Decimal("105"),
                    "volume": 12345,
                    "traded_at": today,
                    "raw": {},
                },
            },
            {
                "status": "error",
                "code": "RATE_LIMIT",
                "message": "rate limit reached",
            },
        ]

        result = refresh_market_prices(force=True, stop_on_rate_limit=True)

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(len(result["failed"]), 1)
        self.assertTrue(result["rate_limited"])
        self.assertGreaterEqual(len(result["skipped"]), 1)
        self.assertEqual(Price.objects.count(), 1)
        self.assertEqual(mock_fetch_alpha_vantage_quote.call_count, 2)

    def test_get_market_summary_uses_latest_price_snapshot(self):
        ensure_index_stocks()
        kospi = Stock.objects.get(symbol="KOSPI")
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        Price.objects.create(
            stock=kospi,
            traded_at=yesterday,
            open_price=Decimal("95"),
            high_price=Decimal("100"),
            low_price=Decimal("90"),
            close_price=Decimal("98"),
            volume=1000,
        )
        Price.objects.create(
            stock=kospi,
            traded_at=today,
            open_price=Decimal("100"),
            high_price=Decimal("112"),
            low_price=Decimal("99"),
            close_price=Decimal("110"),
            volume=1100,
        )

        summary = get_market_summary()
        kospi_row = next(item for item in summary if item["label"] == "KOSPI")

        self.assertEqual(kospi_row["price"], "110.00")
        self.assertEqual(kospi_row["change_rate"], 10.0)
