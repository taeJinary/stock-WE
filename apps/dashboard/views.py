from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render

from services.interest_service import (
    detect_interest_anomalies,
    get_interest_timeline,
    get_sector_interest_heatmap,
    get_top_interest_stocks,
)
from services.stock_service import get_market_summary


def _cached_value(key, *, timeout, builder):
    cached = cache.get(key)
    if cached is not None:
        return cached
    value = builder()
    cache.set(key, value, timeout=timeout)
    return value


def _market_summary_context():
    market_summary = _cached_value(
        "dashboard:market_summary:v1",
        timeout=settings.CACHE_TTL_MARKET_SUMMARY,
        builder=get_market_summary,
    )
    return {
        "market_summary": market_summary,
        "has_market_data": any(float(item["price"].replace(",", "")) > 0 for item in market_summary),
    }


def _top_interest_context():
    top_interest_stocks = _cached_value(
        "dashboard:top_interest:v1",
        timeout=settings.CACHE_TTL_TOP_INTEREST,
        builder=lambda: get_top_interest_stocks(limit=10, only_positive=True),
    )
    return {
        "top_interest_stocks": top_interest_stocks,
        "has_interest_data": len(top_interest_stocks) > 0,
    }


def _interest_heatmap_context():
    sector_heatmap = _cached_value(
        "dashboard:heatmap:v1",
        timeout=settings.CACHE_TTL_HEATMAP,
        builder=lambda: get_sector_interest_heatmap(hours=24, limit=12),
    )
    return {
        "sector_heatmap": sector_heatmap,
        "has_heatmap_data": len(sector_heatmap) > 0,
    }


def _interest_timeline_context():
    interest_timeline = _cached_value(
        "dashboard:timeline:v1",
        timeout=settings.CACHE_TTL_TIMELINE,
        builder=lambda: get_interest_timeline(hours=24),
    )
    return {
        "interest_timeline_data": interest_timeline,
        "has_timeline_data": any(point["mentions"] > 0 for point in interest_timeline),
    }


def _anomaly_alert_context():
    anomaly_alerts = _cached_value(
        "dashboard:anomalies:v1",
        timeout=settings.CACHE_TTL_ANOMALIES,
        builder=lambda: detect_interest_anomalies(limit=8),
    )
    return {
        "anomaly_alerts": anomaly_alerts,
        "has_anomaly_data": len(anomaly_alerts) > 0,
    }


def _dashboard_context():
    return {
        **_market_summary_context(),
        **_top_interest_context(),
        **_anomaly_alert_context(),
        **_interest_heatmap_context(),
        **_interest_timeline_context(),
    }


def dashboard_home(request):
    context = _dashboard_context()
    return render(request, "dashboard/index.html", context)


def market_summary_partial(request):
    context = _market_summary_context()
    return render(request, "dashboard/_market_summary_panel.html", context)


def top_interest_partial(request):
    context = _top_interest_context()
    return render(request, "dashboard/_top_interest_panel.html", context)


def interest_heatmap_partial(request):
    context = _interest_heatmap_context()
    return render(request, "dashboard/_interest_heatmap_panel.html", context)


def interest_timeline_partial(request):
    context = _interest_timeline_context()
    return render(request, "dashboard/_interest_timeline_panel.html", context)


def anomaly_alert_partial(request):
    context = _anomaly_alert_context()
    return render(request, "dashboard/_anomaly_alert_panel.html", context)
