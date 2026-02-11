import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.stocks.models import Interest, Stock
from crawler import NewsCrawler, NaverCrawler, RedditCrawler

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_CRAWLERS = (
    RedditCrawler,
    NaverCrawler,
    NewsCrawler,
)


def _active_target_stocks(limit=20):
    return list(Stock.objects.filter(is_active=True).order_by("symbol")[:limit])


def collect_interest_snapshot(limit_stocks=20, limit_per_symbol=3):
    stocks = _active_target_stocks(limit=limit_stocks)
    if not stocks:
        return {
            "status": "error",
            "code": "NO_STOCKS",
            "message": "No active stocks available for interest collection",
        }

    collected = []
    source_stats = {}
    for crawler_cls in DEFAULT_SOURCE_CRAWLERS:
        crawler = crawler_cls()
        records = crawler.fetch(stocks=stocks, limit_per_symbol=limit_per_symbol)
        source_stats[crawler.source] = len(records)
        collected.extend(records)

    if not collected:
        logger.warning("Interest collection returned zero records")
        return {
            "status": "partial",
            "inserted": 0,
            "sources": source_stats,
            "message": "No mentions were collected from crawlers",
        }

    now = timezone.now()
    grouped = {}
    stock_by_symbol = {stock.symbol: stock for stock in stocks}
    for record in collected:
        stock = stock_by_symbol.get(record.symbol)
        if not stock:
            continue
        key = (stock.id, record.source)
        if key not in grouped:
            grouped[key] = {
                "stock": stock,
                "source": record.source,
                "mentions": 0,
                "samples": [],
            }
        grouped[key]["mentions"] += 1
        if len(grouped[key]["samples"]) < 5:
            grouped[key]["samples"].append(
                {
                    "title": record.title,
                    "url": record.url,
                    "published_at": (
                        record.published_at.isoformat() if record.published_at else None
                    ),
                }
            )

    inserted = 0
    with transaction.atomic():
        for group in grouped.values():
            Interest.objects.create(
                stock=group["stock"],
                source=group["source"],
                recorded_at=now,
                mentions=group["mentions"],
                metadata={"samples": group["samples"]},
            )
            inserted += 1

    return {
        "status": "success",
        "inserted": inserted,
        "sources": source_stats,
        "total_mentions": len(collected),
    }


def get_top_interest_stocks(limit=10, hours=24, only_positive=False):
    since = timezone.now() - timedelta(hours=hours)
    queryset = (
        Stock.objects.filter(is_active=True)
        .annotate(
            total_mentions=Coalesce(
                Sum(
                    "interest_records__mentions",
                    filter=Q(interest_records__recorded_at__gte=since),
                ),
                0,
            )
        )
        .order_by("-total_mentions", "symbol")
    )
    if only_positive:
        queryset = queryset.filter(total_mentions__gt=0)
    return list(queryset[:limit])
