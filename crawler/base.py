import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)


@dataclass
class CrawlRecord:
    source: str
    symbol: str
    title: str
    url: str
    published_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseCrawler:
    source = "base"

    def __init__(self, timeout=10.0):
        self.timeout = timeout

    def fetch(self, stocks, limit_per_symbol=3):
        raise NotImplementedError

    def _safe_get_json(self, url, params=None, headers=None):
        merged_headers = {"User-Agent": "WEStock/1.0 (+https://westock.local)"}
        if headers:
            merged_headers.update(headers)
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, params=params, headers=merged_headers)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[%s] request failed: %s", self.source, exc)
            return None

    def _safe_get_text(self, url, params=None, headers=None):
        merged_headers = {"User-Agent": "WEStock/1.0 (+https://westock.local)"}
        if headers:
            merged_headers.update(headers)
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, params=params, headers=merged_headers)
                response.raise_for_status()
                return response.text
        except httpx.HTTPError as exc:
            logger.warning("[%s] request failed: %s", self.source, exc)
            return ""

    @staticmethod
    def _query(stock):
        return quote_plus(f"{stock.symbol} {stock.name}")
