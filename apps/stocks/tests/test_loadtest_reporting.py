from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from loadtest.reporting import evaluate_thresholds, load_aggregate_metrics


class LoadtestReportingTests(SimpleTestCase):
    def _write_stats_csv(self, directory: Path, lines: list[str]) -> Path:
        csv_path = directory / "stats.csv"
        csv_path.write_text("\n".join(lines), encoding="utf-8")
        return csv_path

    def test_load_aggregate_metrics_reads_aggregated_row(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            csv_path = self._write_stats_csv(
                temp_path,
                [
                    "Type,Name,Request Count,Failure Count,Average Response Time,95%",
                    'GET,GET /api/v1/market/summary/,10,0,100.0,180.0',
                    ",Aggregated,40,1,120.5,250.0",
                ],
            )

            metrics = load_aggregate_metrics(csv_path)

        self.assertEqual(metrics.request_count, 40)
        self.assertEqual(metrics.failure_count, 1)
        self.assertAlmostEqual(metrics.average_response_ms, 120.5)
        self.assertAlmostEqual(metrics.p95_response_ms, 250.0)
        self.assertAlmostEqual(metrics.failure_ratio, 0.025)

    def test_load_aggregate_metrics_raises_when_aggregated_row_missing(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            csv_path = self._write_stats_csv(
                temp_path,
                [
                    "Type,Name,Request Count,Failure Count,Average Response Time,95%",
                    "GET,GET /api/v1/market/summary/,10,0,100.0,180.0",
                ],
            )

            with self.assertRaises(ValueError):
                load_aggregate_metrics(csv_path)

    def test_evaluate_thresholds_returns_failures_when_limits_exceeded(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            csv_path = self._write_stats_csv(
                temp_path,
                [
                    "Type,Name,Request Count,Failure Count,Average Response Time,95%",
                    ",Aggregated,100,4,900.0,1800.0",
                ],
            )
            metrics = load_aggregate_metrics(csv_path)

        failures = evaluate_thresholds(
            metrics,
            max_failure_ratio=0.02,
            max_p95_response_ms=1500.0,
            max_average_response_ms=800.0,
        )

        self.assertEqual(len(failures), 3)

    def test_evaluate_thresholds_returns_empty_when_metrics_are_within_limits(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            csv_path = self._write_stats_csv(
                temp_path,
                [
                    "Type,Name,Request Count,Failure Count,Average Response Time,95%",
                    ",Aggregated,100,1,220.0,480.0",
                ],
            )
            metrics = load_aggregate_metrics(csv_path)

        failures = evaluate_thresholds(
            metrics,
            max_failure_ratio=0.02,
            max_p95_response_ms=1500.0,
            max_average_response_ms=800.0,
        )

        self.assertEqual(failures, [])

