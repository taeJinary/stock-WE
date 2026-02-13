from django.conf import settings
from django.core.cache import cache
from django.db.models import Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.watchlist.models import Watchlist, WatchlistItem
from services.interest_service import get_stock_interest_anomaly
from services.news_service import get_related_news
from services.topic_service import build_stock_topic_cloud
from services.watchlist_service import get_watchlist_limit

from .models import Stock


def _build_stock_detail_payload(stock):
    prices = list(stock.prices.order_by("-traded_at")[:30])[::-1]
    interest = list(stock.interest_records.order_by("-recorded_at")[:50])[::-1]
    news = get_related_news(stock_symbol=stock.symbol, limit=5)
    topic_cloud = build_stock_topic_cloud(stock=stock, hours=72, max_keywords=24)
    stock_anomaly = get_stock_interest_anomaly(stock=stock)
    start_date = timezone.localdate() - timezone.timedelta(days=60)
    interest_by_day = (
        stock.interest_records.filter(recorded_at__date__gte=start_date)
        .annotate(day=TruncDate("recorded_at"))
        .values("day")
        .annotate(total_mentions=Sum("mentions"))
        .order_by("day")
    )

    price_chart_data = [
        {"date": row.traded_at.isoformat(), "close": float(row.close_price)}
        for row in prices
    ]
    interest_chart_data = [
        {"date": row["day"].isoformat(), "mentions": int(row["total_mentions"] or 0)}
        for row in interest_by_day
        if row["day"] is not None
    ]

    return {
        "prices": prices,
        "interest_records": interest,
        "news_items": news,
        "topic_cloud": topic_cloud,
        "stock_anomaly": stock_anomaly,
        "price_chart_data": price_chart_data,
        "interest_chart_data": interest_chart_data,
    }


def _cached_stock_detail_payload(stock):
    cache_key = f"stocks:detail:{stock.symbol}:v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    payload = _build_stock_detail_payload(stock)
    cache.set(
        cache_key,
        payload,
        timeout=settings.CACHE_TTL_STOCK_DETAIL,
    )
    return payload


def stock_list(request):
    query = request.GET.get("q", "").strip()
    stocks = Stock.objects.all()
    if query:
        stocks = stocks.filter(Q(symbol__icontains=query) | Q(name__icontains=query))

    return render(
        request,
        "stocks/list.html",
        {"stocks": stocks[:100], "query": query},
    )


def stock_detail(request, symbol):
    stock = get_object_or_404(Stock, symbol=symbol.upper())
    detail_payload = _cached_stock_detail_payload(stock)

    user_watchlists = []
    watchlist_ids_with_stock = set()
    watchlist_limit = None
    if request.user.is_authenticated:
        user_watchlists = list(
            Watchlist.objects.filter(user=request.user)
            .prefetch_related("items__stock")
            .all()
        )
        watchlist_ids_with_stock = set(
            WatchlistItem.objects.filter(
                watchlist__user=request.user,
                stock=stock,
            ).values_list("watchlist_id", flat=True)
        )
        watchlist_limit = get_watchlist_limit(request.user)

    return render(
        request,
        "stocks/detail.html",
        {
            "stock": stock,
            **detail_payload,
            "watchlists": user_watchlists,
            "watchlist_ids_with_stock": watchlist_ids_with_stock,
            "watchlist_limit": watchlist_limit,
        },
    )
