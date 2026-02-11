from django.shortcuts import render

from services.interest_service import get_top_interest_stocks
from services.stock_service import get_market_summary


def dashboard_home(request):
    context = {
        "market_summary": get_market_summary(),
        "top_interest_stocks": get_top_interest_stocks(limit=10),
    }
    return render(request, "dashboard/index.html", context)
