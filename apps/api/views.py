from django.contrib.auth import authenticate
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import Subscription
from apps.stocks.models import Stock
from services.interest_service import (
    detect_interest_anomalies,
    get_stock_interest_anomaly,
    get_top_interest_stocks,
)
from services.news_service import get_related_news
from services.stock_service import get_market_summary
from services.watchlist_service import get_user_plan

from .pagination import ApiPageNumberPagination
from .permissions import HasApiPlanPermission
from .responses import success_response
from .serializers import (
    InterestAnomalySerializer,
    MarketSummaryItemSerializer,
    StockSummarySerializer,
    TopInterestStockSerializer,
)


def _parse_positive_int(field_name, value, *, default, minimum=1, maximum=365):
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            {field_name: [f"Must be an integer between {minimum} and {maximum}"]}
        ) from exc
    if parsed < minimum or parsed > maximum:
        raise ValidationError({field_name: [f"Must be between {minimum} and {maximum}"]})
    return parsed


class InvalidCredentialsException(APIException):
    status_code = 401
    default_detail = "Invalid username or password."
    default_code = "authentication_failed"


def _require_api_plan_access(user):
    if user.is_superuser or user.is_staff:
        return
    plan = get_user_plan(user)
    if plan not in {Subscription.Plan.PRO, Subscription.Plan.ENTERPRISE}:
        raise PermissionDenied(HasApiPlanPermission.message)


class ApiTokenIssueView(APIView):
    authentication_classes = ()
    permission_classes = ()
    throttle_scope = "auth_token"

    def post(self, request):
        username = str(request.data.get("username", "")).strip()
        password = str(request.data.get("password", ""))

        errors = {}
        if not username:
            errors["username"] = ["This field is required."]
        if not password:
            errors["password"] = ["This field is required."]
        if errors:
            raise ValidationError(errors)

        user = authenticate(request=request, username=username, password=password)
        if user is None or not user.is_active:
            raise InvalidCredentialsException()

        _require_api_plan_access(user)

        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)
        return success_response(
            {
                "token": token.key,
                "token_type": "Token",
                "username": user.username,
            },
            status_code=201,
        )


class BaseProtectedApiView(APIView):
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated, HasApiPlanPermission)
    throttle_scope = "api_read"


class ApiTokenRotateView(BaseProtectedApiView):
    throttle_scope = "auth_token"

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        token = Token.objects.create(user=request.user)
        return success_response(
            {
                "token": token.key,
                "token_type": "Token",
                "username": request.user.username,
            },
            status_code=201,
        )


class MarketSummaryApiView(BaseProtectedApiView):
    def get(self, request):
        rows = get_market_summary()
        serializer = MarketSummaryItemSerializer(rows, many=True)
        return success_response(serializer.data)


class TopInterestApiView(BaseProtectedApiView):
    def get(self, request):
        limit = _parse_positive_int(
            "limit",
            request.query_params.get("limit"),
            default=10,
            maximum=100,
        )
        hours = _parse_positive_int(
            "hours",
            request.query_params.get("hours"),
            default=24,
            maximum=720,
        )
        rows = get_top_interest_stocks(limit=limit, hours=hours, only_positive=True)
        paginator = ApiPageNumberPagination()
        page_rows = paginator.paginate_queryset(rows, request, view=self)
        serializer = TopInterestStockSerializer(page_rows, many=True)
        return paginator.get_paginated_response(serializer.data)


class InterestAnomalyApiView(BaseProtectedApiView):
    def get(self, request):
        limit = _parse_positive_int(
            "limit",
            request.query_params.get("limit"),
            default=8,
            maximum=100,
        )
        recent_hours = _parse_positive_int(
            "recent_hours",
            request.query_params.get("recent_hours"),
            default=6,
            maximum=48,
        )
        baseline_hours = _parse_positive_int(
            "baseline_hours",
            request.query_params.get("baseline_hours"),
            default=72,
            maximum=720,
        )
        rows = detect_interest_anomalies(
            limit=limit,
            recent_hours=recent_hours,
            baseline_hours=baseline_hours,
        )
        paginator = ApiPageNumberPagination()
        page_rows = paginator.paginate_queryset(rows, request, view=self)
        serializer = InterestAnomalySerializer(page_rows, many=True)
        return paginator.get_paginated_response(serializer.data)


class StockSummaryApiView(BaseProtectedApiView):
    def get(self, request, symbol):
        stock = get_object_or_404(Stock, symbol=symbol.upper())
        price_days = _parse_positive_int(
            "price_days",
            request.query_params.get("price_days"),
            default=30,
            maximum=180,
        )
        interest_days = _parse_positive_int(
            "interest_days",
            request.query_params.get("interest_days"),
            default=60,
            maximum=365,
        )
        news_limit = _parse_positive_int(
            "news_limit",
            request.query_params.get("news_limit"),
            default=5,
            maximum=20,
        )

        prices = list(stock.prices.order_by("-traded_at")[:price_days])[::-1]
        latest_price = prices[-1] if prices else None
        price_chart_data = [
            {"date": row.traded_at.isoformat(), "close": float(row.close_price)}
            for row in prices
        ]

        start_date = timezone.localdate() - timezone.timedelta(days=interest_days)
        interest_by_day = (
            stock.interest_records.filter(recorded_at__date__gte=start_date)
            .annotate(day=TruncDate("recorded_at"))
            .values("day")
            .annotate(total_mentions=Sum("mentions"))
            .order_by("day")
        )
        interest_chart_data = [
            {"date": row["day"].isoformat(), "mentions": int(row["total_mentions"] or 0)}
            for row in interest_by_day
            if row["day"] is not None
        ]

        payload = {
            "stock": {
                "symbol": stock.symbol,
                "name": stock.name,
                "market": stock.market,
                "sector": stock.sector,
            },
            "latest_price": (
                {
                    "traded_at": latest_price.traded_at,
                    "open_price": float(latest_price.open_price),
                    "high_price": float(latest_price.high_price),
                    "low_price": float(latest_price.low_price),
                    "close_price": float(latest_price.close_price),
                    "volume": latest_price.volume,
                }
                if latest_price
                else None
            ),
            "price_chart_data": price_chart_data,
            "interest_chart_data": interest_chart_data,
            "news_items": get_related_news(stock_symbol=stock.symbol, limit=news_limit),
            "stock_anomaly": get_stock_interest_anomaly(stock=stock),
        }
        serializer = StockSummarySerializer(payload)
        return success_response(serializer.data)
