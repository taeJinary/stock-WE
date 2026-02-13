from django.urls import path

from .views import (
    InterestAnomalyApiView,
    MarketSummaryApiView,
    StockSummaryApiView,
    TopInterestApiView,
)

app_name = "api"

urlpatterns = [
    path("market/summary/", MarketSummaryApiView.as_view(), name="market-summary"),
    path("interest/top/", TopInterestApiView.as_view(), name="top-interest"),
    path("interest/anomalies/", InterestAnomalyApiView.as_view(), name="interest-anomalies"),
    path("stocks/<str:symbol>/summary/", StockSummaryApiView.as_view(), name="stock-summary"),
]
