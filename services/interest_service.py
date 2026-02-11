import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.stocks.models import Interest, NewsItem, Stock
from crawler import NaverCrawler, RedditCrawler

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_CRAWLERS = (
    RedditCrawler,
    NaverCrawler,
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

    source_stats = {}
    errors = []
    now = timezone.now()
    grouped = {}
    stock_by_symbol = {stock.symbol: stock for stock in stocks}

    for crawler_cls in DEFAULT_SOURCE_CRAWLERS:
        crawler = crawler_cls()
        try:
            records = crawler.fetch(stocks=stocks, limit_per_symbol=limit_per_symbol)
        except Exception as exc:  # pragma: no cover
            logger.error(
                "Interest crawler failed (%s): %s",
                crawler.source,
                exc,
            )
            records = []
            errors.append(
                {
                    "source": crawler.source,
                    "message": str(exc),
                }
            )
        source_stats[crawler.source] = len(records)
        for record in records:
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

    news_since = timezone.now() - timedelta(hours=24)
    news_records = (
        NewsItem.objects.filter(stock__in=stocks, created_at__gte=news_since)
        .order_by("-published_at", "-id")
    )
    news_by_symbol = {}
    for item in news_records:
        bucket = news_by_symbol.setdefault(
            item.stock.symbol,
            {
                "count": 0,
                "samples": [],
            },
        )
        bucket["count"] += 1
        if len(bucket["samples"]) < 5:
            bucket["samples"].append(
                {
                    "title": item.title,
                    "url": item.url,
                    "published_at": item.published_at.isoformat() if item.published_at else None,
                }
            )

    news_total_mentions = 0
    for symbol, payload in news_by_symbol.items():
        stock = stock_by_symbol.get(symbol)
        if not stock:
            continue
        key = (stock.id, Interest.Source.NEWS)
        grouped[key] = {
            "stock": stock,
            "source": Interest.Source.NEWS,
            "mentions": payload["count"],
            "samples": payload["samples"],
        }
        news_total_mentions += payload["count"]
    source_stats[str(Interest.Source.NEWS)] = news_total_mentions

    if not grouped:
        logger.warning("Interest collection returned zero records")
        return {
            "status": "partial",
            "inserted": 0,
            "sources": source_stats,
            "message": "No mentions were collected from sources",
            "errors": errors,
        }

    inserted = 0
    total_mentions = 0
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
            total_mentions += group["mentions"]

    return {
        "status": "success",
        "inserted": inserted,
        "sources": source_stats,
        "total_mentions": total_mentions,
        "errors": errors,
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
