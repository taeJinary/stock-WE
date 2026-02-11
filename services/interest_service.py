import logging
import math
from collections import defaultdict
from datetime import timedelta
from statistics import mean, pstdev

from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.db.models.functions import TruncHour
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


def get_sector_interest_heatmap(hours=24, limit=12):
    since = timezone.now() - timedelta(hours=hours)
    rows = (
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
        .filter(total_mentions__gt=0)
        .values("sector", "total_mentions")
        .order_by("-total_mentions", "sector")
    )

    merged = {}
    for row in rows:
        sector = (row.get("sector") or "").strip() or "Unknown"
        merged[sector] = merged.get(sector, 0) + int(row.get("total_mentions") or 0)

    sorted_items = sorted(
        merged.items(),
        key=lambda item: (-item[1], item[0]),
    )[:limit]
    if not sorted_items:
        return []

    max_mentions = max(mentions for _, mentions in sorted_items) or 1
    return [
        {
            "sector": sector,
            "mentions": mentions,
            "intensity": round(mentions / max_mentions, 4),
        }
        for sector, mentions in sorted_items
    ]


def get_interest_timeline(hours=24):
    end = timezone.now().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=max(hours - 1, 0))

    rows = (
        Interest.objects.filter(recorded_at__gte=start, recorded_at__lte=end)
        .annotate(bucket=TruncHour("recorded_at"))
        .values("bucket")
        .annotate(total_mentions=Sum("mentions"))
        .order_by("bucket")
    )

    mentions_by_bucket = {}
    for row in rows:
        bucket = row.get("bucket")
        if bucket is None:
            continue
        if timezone.is_naive(bucket):
            bucket = timezone.make_aware(bucket, timezone.get_current_timezone())
        label = timezone.localtime(bucket).strftime("%m-%d %H:00")
        mentions_by_bucket[label] = int(row.get("total_mentions") or 0)

    result = []
    current = start
    while current <= end:
        label = timezone.localtime(current).strftime("%m-%d %H:00")
        result.append(
            {
                "label": label,
                "mentions": mentions_by_bucket.get(label, 0),
            }
        )
        current += timedelta(hours=1)
    return result


def _calc_anomaly_metrics(
    recent_values,
    baseline_values,
    min_recent_mentions=8,
    min_surge_ratio=2.5,
    min_z_score=2.0,
):
    recent_total = sum(recent_values)
    if recent_total < min_recent_mentions:
        return None

    baseline_avg = mean(baseline_values) if baseline_values else 0.0
    expected_total = baseline_avg * max(len(recent_values), 1)
    baseline_std = pstdev(baseline_values) if len(baseline_values) >= 2 else 0.0

    if expected_total <= 0:
        surge_ratio = float(recent_total) if recent_total > 0 else 0.0
    else:
        surge_ratio = recent_total / expected_total

    if baseline_std <= 0:
        z_score = 99.0 if recent_total > expected_total else 0.0
    else:
        z_score = (recent_total - expected_total) / (
            baseline_std * math.sqrt(max(len(recent_values), 1))
        )

    if surge_ratio < min_surge_ratio and z_score < min_z_score:
        return None

    severity = "high" if surge_ratio >= 4.0 or z_score >= 4.0 else "medium"
    return {
        "recent_mentions": int(recent_total),
        "expected_mentions": int(round(expected_total)),
        "baseline_hourly_avg": round(baseline_avg, 2),
        "surge_ratio": round(surge_ratio, 2),
        "z_score": round(z_score, 2),
        "severity": severity,
    }


def get_stock_interest_anomaly(
    stock,
    recent_hours=6,
    baseline_hours=72,
    min_recent_mentions=8,
    min_surge_ratio=2.5,
    min_z_score=2.0,
):
    now = timezone.now().replace(minute=0, second=0, microsecond=0)
    recent_start = now - timedelta(hours=max(recent_hours - 1, 0))
    baseline_start = recent_start - timedelta(hours=baseline_hours)

    rows = (
        Interest.objects.filter(
            stock=stock,
            recorded_at__gte=baseline_start,
            recorded_at__lte=now,
        )
        .annotate(bucket=TruncHour("recorded_at"))
        .values("bucket")
        .annotate(total_mentions=Sum("mentions"))
        .order_by("bucket")
    )

    mentions_by_bucket = {}
    for row in rows:
        bucket = row.get("bucket")
        if bucket is None:
            continue
        if timezone.is_naive(bucket):
            bucket = timezone.make_aware(bucket, timezone.get_current_timezone())
        mentions_by_bucket[bucket] = int(row.get("total_mentions") or 0)

    recent_values = []
    cursor = recent_start
    while cursor <= now:
        recent_values.append(mentions_by_bucket.get(cursor, 0))
        cursor += timedelta(hours=1)

    baseline_values = []
    cursor = baseline_start
    baseline_end = recent_start - timedelta(hours=1)
    while cursor <= baseline_end:
        baseline_values.append(mentions_by_bucket.get(cursor, 0))
        cursor += timedelta(hours=1)

    metrics = _calc_anomaly_metrics(
        recent_values=recent_values,
        baseline_values=baseline_values,
        min_recent_mentions=min_recent_mentions,
        min_surge_ratio=min_surge_ratio,
        min_z_score=min_z_score,
    )
    if not metrics:
        return None

    return {
        "symbol": stock.symbol,
        "name": stock.name,
        **metrics,
    }


def detect_interest_anomalies(
    limit=10,
    recent_hours=6,
    baseline_hours=72,
    min_recent_mentions=8,
    min_surge_ratio=2.5,
    min_z_score=2.0,
):
    target_stocks = list(
        Stock.objects.filter(is_active=True).only("id", "symbol", "name").order_by("symbol")
    )
    if not target_stocks:
        return []

    now = timezone.now().replace(minute=0, second=0, microsecond=0)
    recent_start = now - timedelta(hours=max(recent_hours - 1, 0))
    baseline_start = recent_start - timedelta(hours=baseline_hours)
    baseline_end = recent_start - timedelta(hours=1)
    stock_ids = [stock.id for stock in target_stocks]

    rows = (
        Interest.objects.filter(
            stock_id__in=stock_ids,
            recorded_at__gte=baseline_start,
            recorded_at__lte=now,
        )
        .annotate(bucket=TruncHour("recorded_at"))
        .values("stock_id", "bucket")
        .annotate(total_mentions=Sum("mentions"))
        .order_by("stock_id", "bucket")
    )

    mentions_by_stock_bucket = defaultdict(dict)
    for row in rows:
        bucket = row.get("bucket")
        if bucket is None:
            continue
        if timezone.is_naive(bucket):
            bucket = timezone.make_aware(bucket, timezone.get_current_timezone())
        mentions_by_stock_bucket[row["stock_id"]][bucket] = int(row.get("total_mentions") or 0)

    anomalies = []
    for stock in target_stocks:
        stock_mentions = mentions_by_stock_bucket.get(stock.id, {})

        recent_values = []
        cursor = recent_start
        while cursor <= now:
            recent_values.append(stock_mentions.get(cursor, 0))
            cursor += timedelta(hours=1)

        baseline_values = []
        cursor = baseline_start
        while cursor <= baseline_end:
            baseline_values.append(stock_mentions.get(cursor, 0))
            cursor += timedelta(hours=1)

        metrics = _calc_anomaly_metrics(
            recent_values=recent_values,
            baseline_values=baseline_values,
            min_recent_mentions=min_recent_mentions,
            min_surge_ratio=min_surge_ratio,
            min_z_score=min_z_score,
        )
        if not metrics:
            continue

        anomalies.append(
            {
                "symbol": stock.symbol,
                "name": stock.name,
                **metrics,
            }
        )

    anomalies.sort(
        key=lambda row: (
            0 if row["severity"] == "high" else 1,
            -row["surge_ratio"],
            -row["z_score"],
            row["symbol"],
        )
    )
    return anomalies[:limit]
