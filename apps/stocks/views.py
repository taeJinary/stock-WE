from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from services.news_service import get_related_news

from .models import Stock


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
    prices = list(stock.prices.order_by("-traded_at")[:30])[::-1]
    interest = list(stock.interest_records.order_by("-recorded_at")[:50])[::-1]
    news = get_related_news(stock_symbol=stock.symbol, limit=5)

    return render(
        request,
        "stocks/detail.html",
        {
            "stock": stock,
            "prices": prices,
            "interest_records": interest,
            "news_items": news,
        },
    )
