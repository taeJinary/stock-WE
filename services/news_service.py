from apps.stocks.models import Interest


def get_related_news(stock_symbol, limit=5):
    # Placeholder until external news crawler is connected.
    news_records = (
        Interest.objects.filter(stock__symbol=stock_symbol, source=Interest.Source.NEWS)
        .order_by("-recorded_at")[:limit]
    )
    return [
        {
            "title": f"{stock_symbol} news mention ({record.mentions})",
            "url": record.metadata.get("url", "#"),
        }
        for record in news_records
    ]
