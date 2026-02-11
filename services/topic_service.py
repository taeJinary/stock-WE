import re
from collections import Counter
from datetime import timedelta

from django.utils import timezone

from apps.stocks.models import Interest, NewsItem

TOKEN_PATTERN = re.compile(r"[A-Za-z]{2,}|[가-힣]{2,}")
MAX_TEXT_SAMPLES = 200

STOPWORDS = {
    "stock",
    "stocks",
    "market",
    "news",
    "today",
    "update",
    "breaking",
    "finance",
    "financial",
    "investing",
    "analysis",
    "report",
    "korea",
    "usa",
    "global",
    "관련",
    "속보",
    "단독",
    "시장",
    "증시",
    "종목",
    "주식",
    "투자",
    "분석",
    "브리핑",
    "관심도",
    "이슈",
    "뉴스",
}


def _normalize_stopwords(stock):
    dynamic = set(STOPWORDS)
    dynamic.add(stock.symbol.lower())
    for token in TOKEN_PATTERN.findall(stock.name.lower()):
        dynamic.add(token)
    return dynamic


def _extract_tokens(text, stopwords):
    if not text:
        return []
    tokens = []
    for raw in TOKEN_PATTERN.findall(text.lower()):
        token = raw.strip()
        if len(token) < 2:
            continue
        if token in stopwords:
            continue
        tokens.append(token)
    return tokens


def _collect_text_samples(stock, hours):
    since = timezone.now() - timedelta(hours=hours)

    news_titles = list(
        NewsItem.objects.filter(stock=stock, created_at__gte=since)
        .order_by("-published_at", "-id")
        .values_list("title", flat=True)[:120]
    )

    sample_titles = []
    records = (
        Interest.objects.filter(stock=stock, recorded_at__gte=since)
        .order_by("-recorded_at", "-id")[:80]
    )
    for record in records:
        samples = (record.metadata or {}).get("samples", [])
        if not isinstance(samples, list):
            continue
        for item in samples:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if title:
                sample_titles.append(title)

    merged = news_titles + sample_titles
    return merged[:MAX_TEXT_SAMPLES]


def build_stock_topic_cloud(stock, hours=72, max_keywords=24):
    text_samples = _collect_text_samples(stock=stock, hours=hours)
    if not text_samples:
        return []

    stopwords = _normalize_stopwords(stock)
    counter = Counter()
    for text in text_samples:
        counter.update(_extract_tokens(text, stopwords))

    if not counter:
        return []

    most_common = counter.most_common(max_keywords)
    max_count = most_common[0][1] if most_common else 1
    if max_count <= 0:
        max_count = 1

    result = []
    for keyword, count in most_common:
        weight = count / max_count
        # 0.86rem ~ 1.6rem
        font_size = round(0.86 + (0.74 * weight), 3)
        result.append(
            {
                "keyword": keyword,
                "count": count,
                "weight": round(weight, 4),
                "font_size": font_size,
            }
        )
    return result
