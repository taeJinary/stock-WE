from types import SimpleNamespace

from django.test import SimpleTestCase

from crawler.base import BaseCrawler, CrawlRecord


class DummyCrawler(BaseCrawler):
    source = "dummy"

    def fetch(self, stocks, limit_per_symbol=3):
        raise NotImplementedError


class BaseCrawlerParallelTests(SimpleTestCase):
    def test_fetch_in_parallel_collects_records_for_all_stocks(self):
        crawler = DummyCrawler()
        stocks = [
            SimpleNamespace(symbol="AAA", name="AAA Corp"),
            SimpleNamespace(symbol="BBB", name="BBB Corp"),
            SimpleNamespace(symbol="CCC", name="CCC Corp"),
        ]

        def fetch_one(stock):
            return [
                CrawlRecord(
                    source=crawler.source,
                    symbol=stock.symbol,
                    title=f"{stock.symbol} mention",
                    url=f"https://example.com/{stock.symbol.lower()}",
                )
            ]

        rows = crawler._fetch_in_parallel(stocks=stocks, fetch_per_stock=fetch_one, max_workers=3)

        self.assertEqual(len(rows), 3)
        self.assertEqual([row.symbol for row in rows], ["AAA", "BBB", "CCC"])

    def test_fetch_in_parallel_continues_when_single_stock_fetch_fails(self):
        crawler = DummyCrawler()
        stocks = [
            SimpleNamespace(symbol="AAA", name="AAA Corp"),
            SimpleNamespace(symbol="BAD", name="Bad Corp"),
            SimpleNamespace(symbol="CCC", name="CCC Corp"),
        ]

        def fetch_one(stock):
            if stock.symbol == "BAD":
                raise RuntimeError("boom")
            return [
                CrawlRecord(
                    source=crawler.source,
                    symbol=stock.symbol,
                    title=f"{stock.symbol} mention",
                    url=f"https://example.com/{stock.symbol.lower()}",
                )
            ]

        with self.assertLogs("crawler.base", level="WARNING") as captured:
            rows = crawler._fetch_in_parallel(
                stocks=stocks,
                fetch_per_stock=fetch_one,
                max_workers=3,
            )

        self.assertEqual(len(rows), 2)
        self.assertEqual([row.symbol for row in rows], ["AAA", "CCC"])
        self.assertTrue(any("stock fetch failed (BAD)" in line for line in captured.output))
