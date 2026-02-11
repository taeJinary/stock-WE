from datetime import datetime

from .base import BaseCrawler, CrawlRecord


class NewsCrawler(BaseCrawler):
    source = "news"
    endpoint = "https://news.google.com/rss/search"

    def fetch(self, stocks, limit_per_symbol=3):
        try:
            from bs4 import BeautifulSoup
        except ModuleNotFoundError:
            return []

        records = []
        for stock in stocks:
            xml_text = self._safe_get_text(
                self.endpoint,
                params={
                    "q": f"{stock.symbol} OR {stock.name}",
                    "hl": "ko",
                    "gl": "KR",
                    "ceid": "KR:ko",
                },
            )
            if not xml_text:
                continue

            soup = BeautifulSoup(xml_text, "html.parser")
            items = soup.find_all("item")
            for item in items[:limit_per_symbol]:
                pub_date_tag = item.find("pubDate")
                raw_pub_date = pub_date_tag.get_text(strip=True) if pub_date_tag else ""
                published_at = None
                if raw_pub_date:
                    try:
                        published_at = datetime.strptime(
                            raw_pub_date,
                            "%a, %d %b %Y %H:%M:%S %Z",
                        )
                    except ValueError:
                        published_at = None

                title = item.find("title").get_text(strip=True) if item.find("title") else ""
                link = item.find("link").get_text(strip=True) if item.find("link") else ""
                if not title or not link:
                    continue
                records.append(
                    CrawlRecord(
                        source=self.source,
                        symbol=stock.symbol,
                        title=title,
                        url=link,
                        published_at=published_at,
                        metadata={},
                    )
                )
        return records
