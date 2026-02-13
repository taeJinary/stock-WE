from .base import BaseCrawler, CrawlRecord


class NaverCrawler(BaseCrawler):
    source = "naver"
    endpoint = "https://search.naver.com/search.naver"

    def fetch(self, stocks, limit_per_symbol=3):
        try:
            from bs4 import BeautifulSoup
        except ModuleNotFoundError:
            return []

        def _fetch_for_stock(stock):
            records = []
            html = self._safe_get_text(
                self.endpoint,
                params={"where": "news", "query": f"{stock.symbol} {stock.name}"},
            )
            if not html:
                return records

            soup = BeautifulSoup(html, "html.parser")
            links = soup.select("a.news_tit")
            for link in links[:limit_per_symbol]:
                title = (link.get("title") or link.get_text(strip=True) or "").strip()
                url = (link.get("href") or "").strip()
                if not title or not url:
                    continue
                records.append(
                    CrawlRecord(
                        source=self.source,
                        symbol=stock.symbol,
                        title=title,
                        url=url,
                        metadata={},
                    )
                )
            return records

        return self._fetch_in_parallel(
            stocks=stocks,
            fetch_per_stock=_fetch_for_stock,
        )
