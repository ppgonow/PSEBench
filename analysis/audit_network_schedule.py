#!/usr/bin/env python3
"""Reconstruct network-schedule results from the released detail CSV."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import statistics
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from run_http_commit_race import load_scenarios  # noqa: E402


PROFILE_ATTEMPTS = {
    "single": (1, False),
    "delayed-40ms": (1, False),
    "duplicate-downstream": (1, True),
    "concurrent-retry": (2, False),
    "reordered-retry": (2, False),
}
POLICIES = ("check-once", "receipt-bound")


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(quantile * len(ordered)) - 1)]


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for profile in PROFILE_ATTEMPTS:
        for policy in POLICIES:
            selected = [
                row
                for row in rows
                if row["profile"] == profile and row["policy"] == policy
            ]
            attacks = [row for row in selected if row["scenario_type"] == "attack"]
            controls = [row for row in selected if row["scenario_type"] == "benign"]
            latencies = [float(row["profile_e2e_us"]) for row in selected]
            output.append(
                {
                    "profile": profile,
                    "policy": policy,
                    "rows": len(selected),
                    "attack_n": len(attacks),
                    "attack_yes": sum(int(row["attack"]) for row in attacks),
                    "control_n": len(controls),
                    "task_yes": sum(int(row["task"]) for row in controls),
                    "gateway_attempts": sum(int(row["gateway_attempts"]) for row in selected),
                    "delivery_attempts": sum(int(row["delivery_attempts"]) for row in selected),
                    "ledger_rows": sum(int(row["ledger_rows"]) for row in selected),
                    "active_attack_rows": sum(
                        int(row["mutation_active_gate"]) for row in attacks
                    ),
                    "reorder_pass_rows": sum(int(row["reorder_gate"]) for row in selected),
                    "client_p50_us": round(percentile(latencies, 0.50), 3),
                    "client_p95_us": round(percentile(latencies, 0.95), 3),
                    "client_p99_us": round(percentile(latencies, 0.99), 3),
                    "client_median_us": round(statistics.median(latencies), 3),
                }
            )
    return output


def validate(rows: list[dict[str, Any]], scenario_dir: Path) -> dict[str, int]:
    scenarios = load_scenarios(scenario_dir)
    types = {str(row["id"]): str(row["type"]) for row in scenarios}
    expected = {
        (profile, policy, scenario_id)
        for profile in PROFILE_ATTEMPTS
        for policy in POLICIES
        for scenario_id in types
    }
    observed = {
        (row["profile"], row["policy"], row["scenario_id"])
        for row in rows
    }
    if len(rows) != 1500 or observed != expected:
        raise ValueError("detail does not contain the frozen 1,500-row matrix")
    for row in rows:
        attempts, duplicate = PROFILE_ATTEMPTS[row["profile"]]
        is_attack = types[row["scenario_id"]] == "attack"
        expected_allow = row["policy"] == "check-once" or not is_attack
        expected_deliveries = 0
        if expected_allow:
            expected_deliveries = 2 if duplicate else attempts
        if (
            row["scenario_type"] != types[row["scenario_id"]]
            or int(row["committed"]) != int(expected_allow)
            or int(row["attack"]) != int(expected_allow and is_attack)
            or int(row["task"]) != int(expected_allow and not is_attack)
            or int(row["gateway_attempts"]) != attempts
            or int(row["delivery_attempts"]) != expected_deliveries
            or int(row["ledger_rows"]) != int(expected_allow)
            or int(row["role_distinct"]) != 1
            or (is_attack and int(row["mutation_active_gate"]) != 1)
            or int(row["reorder_gate"]) != 1
            or (
                row["profile"] == "reordered-retry"
                and row["logical_arrival_order"] != "2;1"
            )
        ):
            raise ValueError(f"row invariant failed: {row}")
    totals = {
        "rows": len(rows),
        "gateway_attempts": sum(int(row["gateway_attempts"]) for row in rows),
        "delivery_attempts": sum(int(row["delivery_attempts"]) for row in rows),
        "ledger_rows": sum(int(row["ledger_rows"]) for row in rows),
        "active_attack_rows": sum(
            int(row["mutation_active_gate"])
            for row in rows
            if row["scenario_type"] == "attack"
        ),
        "reordered_rows": sum(
            1 for row in rows if row["profile"] == "reordered-retry"
        ),
    }
    frozen = {
        "rows": 1500,
        "gateway_attempts": 2100,
        "delivery_attempts": 1600,
        "ledger_rows": 1000,
        "active_attack_rows": 1000,
        "reordered_rows": 300,
    }
    if totals != frozen:
        raise ValueError(f"frozen totals mismatch: {totals}")
    return totals


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--detail", type=Path, required=True)
    parser.add_argument(
        "--scenario-dir",
        type=Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = read_csv(args.detail)
    totals = validate(rows, args.scenario_dir)
    write_csv(args.output, summarize(rows))
    print(f"network schedule audit passed: {totals}")


if __name__ == "__main__":
    main()
