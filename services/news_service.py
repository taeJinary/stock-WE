import logging
from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.stocks.models import NewsItem, Stock
from crawler import NewsCrawler

logger = logging.getLogger(__name__)


def _active_target_stocks(limit=20):
    return list(Stock.objects.filter(is_active=True).order_by("symbol")[:limit])


def _normalize_datetime(value):
    if value is None:
        return None
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def collect_news_items(limit_stocks=20, limit_per_symbol=3):
    stocks = _active_target_stocks(limit=limit_stocks)
    if not stocks:
        return {
            "status": "error",
            "code": "NO_STOCKS",
            "message": "No active stocks available for news collection",
        }

    crawler = NewsCrawler()
    try:
        records = crawler.fetch(stocks=stocks, limit_per_symbol=limit_per_symbol)
    except Exception as exc:  # pragma: no cover
        logger.error("News crawler failed (%s): %s", crawler.source, exc)
        return {
            "status": "error",
            "code": "CRAWLER_ERROR",
            "message": str(exc),
        }

    if not records:
        return {
            "status": "partial",
            "inserted": 0,
            "updated": 0,
            "message": "No news records were collected from crawler",
        }

    stock_by_symbol = {stock.symbol: stock for stock in stocks}
    inserted = 0
    updated = 0

    with transaction.atomic():
        for record in records:
            stock = stock_by_symbol.get(record.symbol)
            if not stock or not record.title or not record.url:
                continue

            publisher = (record.metadata or {}).get("publisher", "")
            defaults = {
                "source": record.source or NewsItem.Source.NEWS,
                "title": record.title[:300],
                "publisher": publisher[:120],
                "published_at": _normalize_datetime(record.published_at),
                "metadata": record.metadata or {},
            }
            _, created = NewsItem.objects.update_or_create(
                stock=stock,
                url=record.url[:500],
                defaults=defaults,
            )
            if created:
                inserted += 1
            else:
                updated += 1

    return {
        "status": "success",
        "inserted": inserted,
        "updated": updated,
        "total_records": len(records),
    }


def get_related_news(stock_symbol, limit=5):
    news_records = (
        NewsItem.objects.filter(stock__symbol=stock_symbol)
        .order_by("-published_at", "-id")[:limit]
    )
    return [
        {
            "title": record.title,
            "url": record.url,
            "publisher": record.publisher,
            "published_at": record.published_at,
        }
        for record in news_records
    ]


def get_latest_news_for_symbols(symbols, limit_per_symbol=2, since_hours=24):
    if not symbols or limit_per_symbol <= 0:
        return []

    since = timezone.now() - timedelta(hours=since_hours)
    symbol_order = list(dict.fromkeys(symbols))
    grouped_records = defaultdict(list)
    records = (
        NewsItem.objects.filter(stock__symbol__in=symbol_order, created_at__gte=since)
        .select_related("stock")
        .order_by("stock__symbol", "-published_at", "-id")
    )
    for record in records:
        symbol = record.stock.symbol
        bucket = grouped_records[symbol]
        if len(bucket) >= limit_per_symbol:
            continue
        bucket.append(record)

    payload = []
    for symbol in symbol_order:
        for record in grouped_records.get(symbol, []):
            payload.append(
                {
                    "symbol": symbol,
                    "title": record.title,
                    "publisher": record.publisher,
                }
            )
    return payload
