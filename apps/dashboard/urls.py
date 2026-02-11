from django.urls import path

from .views import (
    dashboard_home,
    interest_heatmap_partial,
    interest_timeline_partial,
    market_summary_partial,
    top_interest_partial,
)

app_name = "dashboard"

urlpatterns = [
    path("", dashboard_home, name="home"),
    path("partials/market-summary/", market_summary_partial, name="market-summary-partial"),
    path("partials/top-interest/", top_interest_partial, name="top-interest-partial"),
    path("partials/interest-heatmap/", interest_heatmap_partial, name="interest-heatmap-partial"),
    path("partials/interest-timeline/", interest_timeline_partial, name="interest-timeline-partial"),
]
