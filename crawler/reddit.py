from datetime import datetime, timezone

from .base import BaseCrawler, CrawlRecord


class RedditCrawler(BaseCrawler):
    source = "reddit"
    endpoint = "https://www.reddit.com/search.json"

    def fetch(self, stocks, limit_per_symbol=3):
        def _fetch_for_stock(stock):
            records = []
            payload = self._safe_get_json(
                self.endpoint,
                params={
                    "q": f"{stock.symbol} OR {stock.name}",
                    "sort": "new",
                    "limit": limit_per_symbol,
                },
            )
            if not payload:
                return records

            children = payload.get("data", {}).get("children", [])
            for item in children[:limit_per_symbol]:
                data = item.get("data", {})
                created = data.get("created_utc")
                published_at = None
                if created:
                    published_at = datetime.fromtimestamp(created, tz=timezone.utc)
                records.append(
                    CrawlRecord(
                        source=self.source,
                        symbol=stock.symbol,
                        title=data.get("title", "").strip() or f"{stock.symbol} mention",
                        url=f"https://www.reddit.com{data.get('permalink', '')}",
                        published_at=published_at,
                        metadata={"subreddit": data.get("subreddit", "")},
                    )
                )
            return records

        return self._fetch_in_parallel(
            stocks=stocks,
            fetch_per_stock=_fetch_for_stock,
        )
