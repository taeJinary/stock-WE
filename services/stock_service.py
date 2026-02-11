import logging
import time
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx
from django.conf import settings
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from apps.stocks.models import Price, Stock

logger = logging.getLogger(__name__)

ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"
ALPHA_VANTAGE_MIN_INTERVAL_SEC = 1.1
ALPHA_VANTAGE_MAX_RETRIES = 3

INDEX_DEFINITIONS = {
    "KOSPI": {
        "label": "KOSPI",
        "symbol": "KOSPI",
        "api_symbol": "^KS11",
        "name": "Korea Composite Stock Price Index",
        "market": Stock.Market.KOREA,
    },
    "KOSDAQ": {
        "label": "KOSDAQ",
        "symbol": "KOSDAQ",
        "api_symbol": "^KQ11",
        "name": "KOSDAQ Composite Index",
        "market": Stock.Market.KOREA,
    },
    "S&P 500": {
        "label": "S&P 500",
        "symbol": "SPX",
        "api_symbol": "^GSPC",
        "name": "S&P 500 Index",
        "market": Stock.Market.USA,
    },
    "NASDAQ": {
        "label": "NASDAQ",
        "symbol": "IXIC",
        "api_symbol": "^IXIC",
        "name": "NASDAQ Composite",
        "market": Stock.Market.USA,
    },
}


def _to_decimal(value, default=Decimal("0")):
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _to_date(value):
    if not value:
        return timezone.localdate()
    try:
        return date.fromisoformat(value)
    except ValueError:
        return timezone.localdate()


def _is_rate_limited_message(message):
    if not message:
        return False
    normalized = str(message).lower()
    return (
        "rate limit" in normalized
        or "please consider spreading out your free api requests" in normalized
        or "premium plans" in normalized
    )


def ensure_index_stocks():
    created_count = 0
    updated_count = 0
    with transaction.atomic():
        for definition in INDEX_DEFINITIONS.values():
            stock, created = Stock.objects.update_or_create(
                symbol=definition["symbol"],
                defaults={
                    "name": definition["name"],
                    "market": definition["market"],
                    "sector": "INDEX",
                    "is_active": True,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
    return {
        "status": "success",
        "created": created_count,
        "updated": updated_count,
    }


def fetch_alpha_vantage_quote(symbol, max_retries=ALPHA_VANTAGE_MAX_RETRIES):
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": settings.ALPHA_VANTAGE_API_KEY,
    }
    last_error = ""

    for attempt in range(1, max_retries + 1):
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(ALPHA_VANTAGE_BASE_URL, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            last_error = str(exc)
            logger.error(
                "Alpha Vantage quote request failed (%s, attempt %s/%s): %s",
                symbol,
                attempt,
                max_retries,
                exc,
            )
            if attempt < max_retries:
                time.sleep(ALPHA_VANTAGE_MIN_INTERVAL_SEC * attempt)
                continue
            return {"status": "error", "code": "API_ERROR", "message": last_error}

        quote = payload.get("Global Quote") or {}
        if quote and quote.get("05. price"):
            return {
                "status": "success",
                "data": {
                    "open_price": _to_decimal(quote.get("02. open")),
                    "high_price": _to_decimal(quote.get("03. high")),
                    "low_price": _to_decimal(quote.get("04. low")),
                    "close_price": _to_decimal(quote.get("05. price")),
                    "volume": int(float(quote.get("06. volume") or 0)),
                    "traded_at": _to_date(quote.get("07. latest trading day")),
                    "raw": quote,
                },
            }

        note = payload.get("Note") or payload.get("Information") or "Empty quote payload"
        last_error = str(note)
        if _is_rate_limited_message(note):
            logger.warning(
                "Alpha Vantage rate-limited (%s, attempt %s/%s): %s",
                symbol,
                attempt,
                max_retries,
                note,
            )
            if attempt < max_retries:
                time.sleep(ALPHA_VANTAGE_MIN_INTERVAL_SEC * attempt)
                continue
            return {"status": "error", "code": "RATE_LIMIT", "message": last_error}

        logger.warning("Alpha Vantage empty quote (%s): %s", symbol, note)
        return {"status": "error", "code": "EMPTY_QUOTE", "message": str(note)}

    return {"status": "error", "code": "UNKNOWN", "message": last_error or "Unknown error"}


def refresh_market_prices(symbols=None, force=False):
    ensure_index_stocks()
    if symbols:
        stock_queryset = Stock.objects.filter(symbol__in=symbols, is_active=True)
    else:
        index_symbols = [item["symbol"] for item in INDEX_DEFINITIONS.values()]
        stock_queryset = Stock.objects.filter(symbol__in=index_symbols, is_active=True)

    inserted = 0
    updated = 0
    skipped = []
    failed = []
    today = timezone.localdate()
    api_call_count = 0
    for stock in stock_queryset:
        if not force and Price.objects.filter(stock=stock, traded_at=today).exists():
            skipped.append(stock.symbol)
            continue

        api_symbol = stock.symbol
        for definition in INDEX_DEFINITIONS.values():
            if definition["symbol"] == stock.symbol:
                api_symbol = definition["api_symbol"]
                break

        if api_call_count > 0:
            time.sleep(ALPHA_VANTAGE_MIN_INTERVAL_SEC)
        api_call_count += 1
        quote_result = fetch_alpha_vantage_quote(api_symbol)
        if quote_result["status"] != "success":
            failed.append(
                {
                    "symbol": stock.symbol,
                    "reason": quote_result.get("code", "UNKNOWN"),
                    "message": quote_result.get("message", ""),
                }
            )
            continue

        quote = quote_result["data"]
        _, created = Price.objects.update_or_create(
            stock=stock,
            traded_at=quote["traded_at"],
            defaults={
                "open_price": quote["open_price"],
                "high_price": quote["high_price"],
                "low_price": quote["low_price"],
                "close_price": quote["close_price"],
                "volume": quote["volume"],
            },
        )
        if created:
            inserted += 1
        else:
            updated += 1

    status = "success" if not failed else "partial"
    return {
        "status": status,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
    }


def get_market_summary():
    symbols = [item["symbol"] for item in INDEX_DEFINITIONS.values()]
    stocks = Stock.objects.filter(symbol__in=symbols)

    latest_price_subquery = Price.objects.filter(
        stock=OuterRef("pk")
    ).order_by("-traded_at", "-id")

    stocks = stocks.annotate(
        latest_close=Subquery(latest_price_subquery.values("close_price")[:1]),
        latest_open=Subquery(latest_price_subquery.values("open_price")[:1]),
    )

    by_symbol = {stock.symbol: stock for stock in stocks}
    summary = []
    for definition in INDEX_DEFINITIONS.values():
        stock = by_symbol.get(definition["symbol"])
        price = float(stock.latest_close) if stock and stock.latest_close is not None else 0.0
        open_price = float(stock.latest_open) if stock and stock.latest_open is not None else 0.0
        change_rate = 0.0
        if open_price > 0:
            change_rate = round(((price - open_price) / open_price) * 100, 2)
        summary.append(
            {
                "label": definition["label"],
                "price": f"{price:,.2f}",
                "change_rate": change_rate,
            }
        )
    return summary
