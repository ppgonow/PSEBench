#!/usr/bin/env python3
"""Benchmark stable check-to-commit traffic through the three-process HTTP path."""

from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import pathlib
import secrets
import statistics
import sys
import time
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from run_http_commit_race import load_scenarios  # noqa: E402
from run_multiprocess_commit_race import (  # noqa: E402
    PersistentJsonPool,
    ServiceCluster,
    percentile,
)


POLICIES = ("check-once", "receipt-bound")


def run_request(
    cluster: ServiceCluster,
    scenario: dict[str, Any],
    policy: str,
    trial_id: str,
    authorization_pool: PersistentJsonPool,
    gateway_pool: PersistentJsonPool,
) -> dict[str, Any]:
    race = scenario["commit_race"]
    started_ns = time.perf_counter_ns()
    checked = authorization_pool.post(
        "/check",
        {
            "trial_id": trial_id,
            "policy": policy,
            "authorized_effect": race["authorized_effect"],
            "checked_effect": race["checked_effect"],
            "check_context": race["check_context"],
        },
    )
    committed = gateway_pool.post(
        "/commit",
        {
            "trial_id": trial_id,
            "policy": policy,
            "receipt": checked["receipt"],
            "commit_effect": race["commit_effect"],
            "duplicate_delivery": False,
        },
    )
    client_e2e_us = (time.perf_counter_ns() - started_ns) / 1000.0
    if (
        not committed["committed"]
        or int(committed["ledger_rows"]) != 1
        or int(committed["delivery_attempts"]) != 1
    ):
        raise RuntimeError(f"stable load request failed: {trial_id}: {committed}")
    return {
        "trial_id": trial_id,
        "policy": policy,
        "client_e2e_us": round(client_e2e_us, 3),
        "gateway_total_us": float(committed["gateway_total_us"]),
        "auth_query_us": float(committed["auth_query_us"]),
        "service_call_us": float(committed["service_call_us"]),
        "committed": 1,
        "ledger_rows": int(committed["ledger_rows"]),
        "delivery_attempts": int(committed["delivery_attempts"]),
    }


def run_condition(
    cluster: ServiceCluster,
    scenario: dict[str, Any],
    *,
    policy: str,
    concurrency: int,
    repeat: int,
    requests: int,
    warmup: int,
    authorization_pool: PersistentJsonPool,
    gateway_pool: PersistentJsonPool,
) -> list[dict[str, Any]]:
    def execute(index: int, measured: bool) -> dict[str, Any]:
        phase = "measure" if measured else "warmup"
        trial_id = f"load:{policy}:c{concurrency}:r{repeat}:{phase}:{index:04d}"
        return run_request(
            cluster,
            scenario,
            policy,
            trial_id,
            authorization_pool,
            gateway_pool,
        )

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        list(executor.map(lambda index: execute(index, False), range(warmup)))
        started = time.perf_counter()
        rows = list(executor.map(lambda index: execute(index, True), range(requests)))
        wall_s = time.perf_counter() - started
    for index, row in enumerate(rows):
        row.update(
            {
                "concurrency": concurrency,
                "repeat": repeat,
                "request_index": index,
                "condition_wall_s": round(wall_s, 6),
                "condition_throughput_rps": round(requests / wall_s, 6),
            }
        )
    return rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for policy in POLICIES:
        levels = sorted({int(row["concurrency"]) for row in rows if row["policy"] == policy})
        for concurrency in levels:
            selected = [
                row
                for row in rows
                if row["policy"] == policy and int(row["concurrency"]) == concurrency
            ]
            repeats = sorted({int(row["repeat"]) for row in selected})
            throughputs = [
                float(next(row for row in selected if int(row["repeat"]) == repeat)["condition_throughput_rps"])
                for repeat in repeats
            ]
            client = [float(row["client_e2e_us"]) for row in selected]
            gateway = [float(row["gateway_total_us"]) for row in selected]
            auth = [float(row["auth_query_us"]) for row in selected]
            service = [float(row["service_call_us"]) for row in selected]
            output.append(
                {
                    "policy": policy,
                    "concurrency": concurrency,
                    "repeats": len(repeats),
                    "requests": len(selected),
                    "committed": sum(int(row["committed"]) for row in selected),
                    "throughput_median_rps": round(statistics.median(throughputs), 3),
                    "throughput_min_rps": round(min(throughputs), 3),
                    "throughput_max_rps": round(max(throughputs), 3),
                    "client_p50_us": round(percentile(client, 0.50), 3),
                    "client_p95_us": round(percentile(client, 0.95), 3),
                    "client_p99_us": round(percentile(client, 0.99), 3),
                    "gateway_p50_us": round(percentile(gateway, 0.50), 3),
                    "gateway_p95_us": round(percentile(gateway, 0.95), 3),
                    "gateway_p99_us": round(percentile(gateway, 0.99), 3),
                    "auth_query_p50_us": round(percentile(auth, 0.50), 3),
                    "service_call_p50_us": round(percentile(service, 0.50), 3),
                }
            )
    return output


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario-dir",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument(
        "--output-root",
        type=pathlib.Path,
        default=ROOT / "results" / "commit_gateway_load",
    )
    parser.add_argument(
        "--analysis-prefix",
        type=pathlib.Path,
        default=ROOT / "analysis" / "commit_gateway_load",
    )
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 8, 32])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--requests-per-repeat", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--state-delay-ms", type=float, default=0.5)
    parser.add_argument("--service-delay-ms", type=float, default=0.5)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()

    if args.pilot:
        args.concurrency = [32]
        args.repeats = 1
        args.requests_per_repeat = 50
        args.warmup = 10
        args.output_root = ROOT / "tmp" / "commit_gateway_load_pilot"
    else:
        if args.concurrency != [1, 8, 32]:
            raise SystemExit("reportable load run requires concurrency levels 1 8 32")
        if args.repeats != 3 or args.requests_per_repeat != 200 or args.warmup != 10:
            raise SystemExit("reportable load run requires 3 repeats, 200 requests, and 10 warmups")
    if args.state_delay_ms != 0.5 or args.service_delay_ms != 0.5:
        raise SystemExit("load run requires fixed 0.5 ms service delays")

    detail_path = pathlib.Path(f"{args.analysis_prefix}_detail.csv")
    summary_path = pathlib.Path(f"{args.analysis_prefix}_summary.csv")
    database_path = args.output_root / "service.sqlite"
    if any(path.exists() for path in (detail_path, summary_path, database_path)) and not args.overwrite:
        raise SystemExit("load output exists; pass --overwrite for a fresh complete run")
    args.output_root.mkdir(parents=True, exist_ok=True)
    if database_path.exists():
        database_path.unlink()

    scenarios = load_scenarios(args.scenario_dir)
    benign = next(row for row in scenarios if row["type"] == "benign")
    rows: list[dict[str, Any]] = []
    with ServiceCluster(
        database_path,
        secrets.token_bytes(32),
        state_delay_ms=args.state_delay_ms,
        service_delay_ms=args.service_delay_ms,
        pooled_http=True,
        pool_size=max(args.concurrency),
    ) as cluster:
        with ExitStack() as stack:
            authorization_pool = stack.enter_context(
                PersistentJsonPool(cluster.urls["authorization"], max(args.concurrency))
            )
            gateway_pool = stack.enter_context(
                PersistentJsonPool(cluster.urls["gateway"], max(args.concurrency))
            )
            for repeat in range(1, args.repeats + 1):
                policy_order = POLICIES if repeat % 2 else tuple(reversed(POLICIES))
                for concurrency in args.concurrency:
                    for policy in policy_order:
                        rows.extend(
                            run_condition(
                                cluster,
                                benign,
                                policy=policy,
                                concurrency=concurrency,
                                repeat=repeat,
                                requests=args.requests_per_repeat,
                                warmup=args.warmup,
                                authorization_pool=authorization_pool,
                                gateway_pool=gateway_pool,
                            )
                        )
    expected = len(POLICIES) * len(args.concurrency) * args.repeats * args.requests_per_repeat
    if len(rows) != expected or any(
        int(row["committed"]) != 1
        or int(row["ledger_rows"]) != 1
        or int(row["delivery_attempts"]) != 1
        for row in rows
    ):
        raise RuntimeError("load matrix failed completeness or ledger checks")
    if args.pilot:
        database_path.unlink(missing_ok=True)
        print(f"load transport pilot passed: requests={len(rows)} concurrency=32")
    else:
        write_csv(detail_path, rows)
        write_csv(summary_path, summarize(rows))
        print(
            f"completed load matrix: requests={len(rows)} "
            f"conditions={len(POLICIES) * len(args.concurrency)}"
        )


if __name__ == "__main__":
    main()
