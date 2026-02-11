import json
import logging
from datetime import datetime

import httpx
from django.conf import settings
from django.utils import timezone

from services.interest_service import get_top_interest_stocks
from services.news_service import get_latest_news_for_symbols
from services.stock_service import get_market_summary

logger = logging.getLogger(__name__)


def _collect_briefing_input():
    market_data = get_market_summary()
    top_interest_stocks = get_top_interest_stocks(limit=6)
    interest_data = [
        {
            "symbol": stock.symbol,
            "name": stock.name,
            "interest": int(getattr(stock, "total_mentions", 0)),
        }
        for stock in top_interest_stocks
    ]

    top_symbols = [stock.symbol for stock in top_interest_stocks[:3]]
    headlines = get_latest_news_for_symbols(top_symbols, limit_per_symbol=2)

    return {
        "generated_at": datetime.now(tz=timezone.get_current_timezone()).isoformat(),
        "market_indices": market_data,
        "top_interest_stocks": interest_data,
        "headlines": headlines,
    }


def _build_prompt(data):
    data_json = json.dumps(data, ensure_ascii=False, indent=2)
    return (
        "당신은 동서양 시장을 모두 분석하는 시니어 애널리스트입니다.\n"
        "아래 JSON 데이터를 바탕으로 한국어 모닝 브리핑을 작성하세요.\n"
        "형식:\n"
        "1) 한 줄 시장 요약\n"
        "2) 주요 지수 동향\n"
        "3) 관심도 급등 종목 3개와 이유\n"
        "4) 오늘의 체크포인트 1개\n"
        "톤: 간결하고 신뢰감 있게.\n"
        "출력: HTML 태그 없이 순수 텍스트.\n\n"
        f"[DATA]\n{data_json}"
    )


def _extract_text_from_gemini(payload):
    candidates = payload.get("candidates", [])
    if not candidates:
        return ""
    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    if not parts:
        return ""
    return parts[0].get("text", "").strip()


def _generate_with_gemini(prompt):
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent"
    params = {"key": settings.GEMINI_API_KEY}
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 900},
    }
    with httpx.Client(timeout=20.0) as client:
        response = client.post(endpoint, params=params, json=body)
        response.raise_for_status()
        text = _extract_text_from_gemini(response.json())
        if not text:
            raise ValueError("Gemini response did not include text output")
        return text


def _build_fallback_summary(data):
    top_symbols = [item["symbol"] for item in data.get("top_interest_stocks", [])[:3]]
    symbol_text = ", ".join(top_symbols) if top_symbols else "데이터 없음"
    return (
        "오늘의 브리핑은 준비 중입니다.\n"
        f"- 관심도 상위 종목: {symbol_text}\n"
        "- 외부 AI 응답이 불안정하여 요약 생성을 재시도하고 있습니다."
    )


def create_daily_briefing(target_date=None):
    from apps.briefing.models import DailyBriefing

    briefing_date = target_date or timezone.localdate()
    data = _collect_briefing_input()
    prompt = _build_prompt(data)

    generated_by = "gemini"
    summary = _build_fallback_summary(data)
    try:
        summary = _generate_with_gemini(prompt)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        generated_by = "gemini-fallback"
        logger.error("Gemini briefing generation failed: %s", exc)

    discussed_symbols = [item["symbol"] for item in data.get("top_interest_stocks", [])]
    briefing, _ = DailyBriefing.objects.update_or_create(
        briefing_date=briefing_date,
        defaults={
            "title": f"{briefing_date} Market Briefing",
            "summary": summary,
            "discussed_symbols": discussed_symbols,
            "generated_by": generated_by,
            "email_status": DailyBriefing.EmailStatus.PENDING,
            "email_sent_count": 0,
            "email_target_count": 0,
            "email_sent_at": None,
            "email_failure_reason": "",
        },
    )
    return briefing
