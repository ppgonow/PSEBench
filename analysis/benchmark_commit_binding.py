#!/usr/bin/env python3
"""Benchmark check-time and commit-bound authorization lifecycle costs."""

from __future__ import annotations

import argparse
import csv
import pathlib
import statistics
import sys
import time

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from commit_binding import (  # noqa: E402
    CheckContext,
    CommitContext,
    issue_receipt,
    verify_commit,
)
from effect_boundary import EffectSpec, check_effect  # noqa: E402
from replay_commit_race import SIMULATION_KEY  # noqa: E402


def percentile(values: list[int], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction)))
    return float(ordered[index])


def load_cases(directory: pathlib.Path) -> list[tuple]:
    cases = []
    for path in sorted(directory.glob("*.yaml")):
        scenario = yaml.safe_load(path.read_text(encoding="utf-8"))
        race = scenario["commit_race"]
        authorized = EffectSpec(**race["authorized_effect"])
        checked = EffectSpec(**race["checked_effect"])
        committed = EffectSpec(**race["commit_effect"])
        check_context = CheckContext(**race["check_context"])
        commit_context = CommitContext(**race["commit_context"])
        receipt = issue_receipt(authorized, checked, check_context, SIMULATION_KEY)
        cases.append(
            (authorized, checked, committed, check_context, commit_context, receipt)
        )
    return cases


def measure(cases: list[tuple], repeats: int, iterations: int) -> list[dict]:
    rows = []
    operations = ("check-once", "receipt-issue", "commit-verify", "bound-lifecycle")
    for repeat in range(1, repeats + 1):
        timings = {operation: [] for operation in operations}
        for _ in range(iterations):
            for authorized, checked, committed, check_context, commit_context, receipt in cases:
                started = time.perf_counter_ns()
                check_effect(authorized, checked)
                timings["check-once"].append(time.perf_counter_ns() - started)

                started = time.perf_counter_ns()
                issue_receipt(authorized, checked, check_context, SIMULATION_KEY)
                timings["receipt-issue"].append(time.perf_counter_ns() - started)

                started = time.perf_counter_ns()
                verify_commit(receipt, committed, commit_context, SIMULATION_KEY)
                timings["commit-verify"].append(time.perf_counter_ns() - started)

                started = time.perf_counter_ns()
                fresh_receipt = issue_receipt(
                    authorized, checked, check_context, SIMULATION_KEY
                )
                verify_commit(fresh_receipt, committed, commit_context, SIMULATION_KEY)
                timings["bound-lifecycle"].append(time.perf_counter_ns() - started)
        for operation in operations:
            values = timings[operation]
            rows.append(
                {
                    "repeat": repeat,
                    "operation": operation,
                    "samples": len(values),
                    "median_us": round(statistics.median(values) / 1000, 6),
                    "p95_us": round(percentile(values, 0.95) / 1000, 6),
                }
            )
    return rows


def aggregate(rows: list[dict]) -> list[dict]:
    output = []
    operations = sorted({row["operation"] for row in rows})
    for operation in operations:
        selected = [row for row in rows if row["operation"] == operation]
        output.append(
            {
                "operation": operation,
                "repeats": len(selected),
                "samples_per_repeat": selected[0]["samples"],
                "median_us_across_repeats": round(
                    statistics.median(row["median_us"] for row in selected), 6
                ),
                "p95_us_across_repeats": round(
                    statistics.median(row["p95_us"] for row in selected), 6
                ),
            }
        )
    return output


def write_csv(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario-dir",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument(
        "--runs-output",
        type=pathlib.Path,
        default=ROOT / "analysis" / "commit_binding_overhead_runs.csv",
    )
    parser.add_argument(
        "--summary-output",
        type=pathlib.Path,
        default=ROOT / "analysis" / "commit_binding_overhead_summary.csv",
    )
    args = parser.parse_args()
    if args.repeats < 1 or args.iterations < 1:
        raise SystemExit("repeats and iterations must be positive")
    cases = load_cases(args.scenario_dir)
    if not cases:
        raise SystemExit(f"no commit-race scenarios under {args.scenario_dir}")
    rows = measure(cases, args.repeats, args.iterations)
    summary = aggregate(rows)
    write_csv(args.runs_output, rows)
    write_csv(args.summary_output, summary)
    print(
        f"benchmarked {len(cases)} cases x {args.iterations} iterations x "
        f"{args.repeats} repeats"
    )


if __name__ == "__main__":
    main()
