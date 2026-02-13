from django.urls import path

from .views import (
    ApiTokenIssueView,
    ApiTokenRotateView,
    InterestAnomalyApiView,
    MarketSummaryApiView,
    StockSummaryApiView,
    TopInterestApiView,
)

app_name = "api"

urlpatterns = [
    path("auth/token/", ApiTokenIssueView.as_view(), name="auth-token-issue"),
    path("auth/token/rotate/", ApiTokenRotateView.as_view(), name="auth-token-rotate"),
    path("market/summary/", MarketSummaryApiView.as_view(), name="market-summary"),
    path("interest/top/", TopInterestApiView.as_view(), name="top-interest"),
    path("interest/anomalies/", InterestAnomalyApiView.as_view(), name="interest-anomalies"),
    path("stocks/<str:symbol>/summary/", StockSummaryApiView.as_view(), name="stock-summary"),
]
