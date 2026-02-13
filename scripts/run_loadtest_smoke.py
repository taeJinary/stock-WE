from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loadtest.reporting import evaluate_thresholds, load_aggregate_metrics


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Locust headless load test and assert baseline thresholds.",
    )
    parser.add_argument("--users", type=int, default=int(os.getenv("LOADTEST_USERS", "30")))
    parser.add_argument("--spawn-rate", type=float, default=float(os.getenv("LOADTEST_SPAWN_RATE", "5")))
    parser.add_argument("--run-time", default=os.getenv("LOADTEST_RUN_TIME", "2m"))
    parser.add_argument("--csv-prefix", default=os.getenv("LOADTEST_CSV_PREFIX", "loadtest/result-smoke"))
    parser.add_argument(
        "--max-failure-ratio",
        type=float,
        default=float(os.getenv("LOADTEST_MAX_FAILURE_RATIO", "0.02")),
    )
    parser.add_argument(
        "--max-p95-ms",
        type=float,
        default=float(os.getenv("LOADTEST_MAX_P95_MS", "1500")),
    )
    parser.add_argument(
        "--max-avg-ms",
        type=float,
        default=float(os.getenv("LOADTEST_MAX_AVG_MS", "800")),
    )
    parser.add_argument(
        "--skip-locust",
        action="store_true",
        help="Skip running Locust and validate an existing CSV output only.",
    )
    return parser.parse_args()


def _build_locust_command(args: argparse.Namespace) -> list[str]:
    return [
        sys.executable,
        "-m",
        "locust",
        "-f",
        "loadtest/locustfile.py",
        "--headless",
        "--users",
        str(args.users),
        "--spawn-rate",
        str(args.spawn_rate),
        "--run-time",
        args.run_time,
        "--csv",
        args.csv_prefix,
    ]


def main() -> int:
    args = _parse_args()
    if not args.skip_locust:
        command = _build_locust_command(args)
        print("[STEP] Run Locust smoke test")
        print(" ".join(command))
        subprocess.run(command, cwd=ROOT, check=True, env=os.environ.copy())

    stats_csv = ROOT / f"{args.csv_prefix}_stats.csv"
    if not stats_csv.exists():
        print(f"[FAIL] stats csv not found: {stats_csv}")
        return 2

    metrics = load_aggregate_metrics(stats_csv)
    threshold_failures = evaluate_thresholds(
        metrics,
        max_failure_ratio=args.max_failure_ratio,
        max_p95_response_ms=args.max_p95_ms,
        max_average_response_ms=args.max_avg_ms,
    )

    print("\n[SUMMARY] aggregate metrics")
    print(f"- request_count: {metrics.request_count}")
    print(f"- failure_count: {metrics.failure_count}")
    print(f"- failure_ratio: {metrics.failure_ratio:.2%}")
    print(f"- avg_response_ms: {metrics.average_response_ms:.2f}")
    print(f"- p95_response_ms: {metrics.p95_response_ms:.2f}")

    if threshold_failures:
        print("\n[FAIL] load test baseline check failed")
        for failure in threshold_failures:
            print(f"- {failure}")
        return 1

    print("\n[OK] load test baseline check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
