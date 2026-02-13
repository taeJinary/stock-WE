from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


AGGREGATED_ROW_NAME = "Aggregated"


@dataclass(frozen=True)
class LoadtestAggregate:
    request_count: int
    failure_count: int
    average_response_ms: float
    p95_response_ms: float

    @property
    def failure_ratio(self) -> float:
        if self.request_count <= 0:
            return 0.0
        return self.failure_count / self.request_count


def _to_int(raw_value: str | None) -> int:
    if raw_value is None:
        return 0
    cleaned = raw_value.strip()
    if not cleaned:
        return 0
    return int(float(cleaned))


def _to_float(raw_value: str | None) -> float:
    if raw_value is None:
        return 0.0
    cleaned = raw_value.strip()
    if not cleaned:
        return 0.0
    return float(cleaned)


def load_aggregate_metrics(stats_csv_path: str | Path) -> LoadtestAggregate:
    csv_path = Path(stats_csv_path)
    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            if row.get("Name", "").strip() != AGGREGATED_ROW_NAME:
                continue
            return LoadtestAggregate(
                request_count=_to_int(row.get("Request Count")),
                failure_count=_to_int(row.get("Failure Count")),
                average_response_ms=_to_float(row.get("Average Response Time")),
                p95_response_ms=_to_float(row.get("95%")),
            )

    raise ValueError(f"Aggregated row not found in {csv_path}")


def evaluate_thresholds(
    metrics: LoadtestAggregate,
    *,
    max_failure_ratio: float,
    max_p95_response_ms: float,
    max_average_response_ms: float,
) -> list[str]:
    failures: list[str] = []
    if metrics.request_count <= 0:
        failures.append("No requests recorded in load test output.")

    if metrics.failure_ratio > max_failure_ratio:
        failures.append(
            "Failure ratio exceeded "
            f"({metrics.failure_ratio:.2%} > {max_failure_ratio:.2%})."
        )

    if metrics.p95_response_ms > max_p95_response_ms:
        failures.append(
            "P95 response time exceeded "
            f"({metrics.p95_response_ms:.2f} ms > {max_p95_response_ms:.2f} ms)."
        )

    if metrics.average_response_ms > max_average_response_ms:
        failures.append(
            "Average response time exceeded "
            f"({metrics.average_response_ms:.2f} ms > {max_average_response_ms:.2f} ms)."
        )

    return failures

