from django.shortcuts import render

from services.interest_service import get_top_interest_stocks
from services.stock_service import get_market_summary


def _dashboard_context():
    market_summary = get_market_summary()
    top_interest_stocks = get_top_interest_stocks(limit=10, only_positive=True)
    return {
        "market_summary": market_summary,
        "top_interest_stocks": top_interest_stocks,
        "has_market_data": any(float(item["price"].replace(",", "")) > 0 for item in market_summary),
        "has_interest_data": len(top_interest_stocks) > 0,
    }


def dashboard_home(request):
    context = _dashboard_context()
    return render(request, "dashboard/index.html", context)


def market_summary_partial(request):
    context = _dashboard_context()
    return render(request, "dashboard/_market_summary_panel.html", context)


def top_interest_partial(request):
    context = _dashboard_context()
    return render(request, "dashboard/_top_interest_panel.html", context)
