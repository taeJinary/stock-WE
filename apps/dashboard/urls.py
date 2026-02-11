from django.urls import path

from .views import dashboard_home, market_summary_partial, top_interest_partial

app_name = "dashboard"

urlpatterns = [
    path("", dashboard_home, name="home"),
    path("partials/market-summary/", market_summary_partial, name="market-summary-partial"),
    path("partials/top-interest/", top_interest_partial, name="top-interest-partial"),
]
