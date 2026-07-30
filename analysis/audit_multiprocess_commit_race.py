#!/usr/bin/env python3
"""Audit the released three-process commit-race detail table."""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from run_http_commit_race import load_scenarios  # noqa: E402
from run_multiprocess_commit_race import (  # noqa: E402
    POLICIES,
    paired,
    summarize,
    validate_complete,
)


INTEGER_FIELDS = {
    "attack",
    "task",
    "committed",
    "valid_at_commit",
    "duplicate_delivery",
    "delivery_attempts",
    "ledger_rows",
    "mutation_before_commit",
    "request_overlap",
    "precommit_mutation_active",
    "authorization_pid",
    "gateway_pid",
    "effect_pid",
}
FLOAT_FIELDS = {"auth_query_us", "service_call_us", "gateway_total_us"}


def read_detail(path: pathlib.Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows: list[dict[str, Any]] = list(csv.DictReader(handle))
    for row in rows:
        for field in INTEGER_FIELDS:
            row[field] = int(row[field])
        for field in FLOAT_FIELDS:
            row[field] = float(row[field])
    return rows


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--detail",
        type=pathlib.Path,
        default=ROOT / "analysis" / "multiprocess_commit_race_detail.csv",
    )
    parser.add_argument(
        "--scenario-dir",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument(
        "--output-prefix",
        type=pathlib.Path,
        default=ROOT / "tmp" / "multiprocess_commit_race_audit",
    )
    args = parser.parse_args()

    rows = read_detail(args.detail)
    scenarios = load_scenarios(args.scenario_dir)
    role_pids = {
        "authorization": next(iter({row["authorization_pid"] for row in rows})),
        "gateway": next(iter({row["gateway_pid"] for row in rows})),
        "effect": next(iter({row["effect_pid"] for row in rows})),
    }
    if any(len({row[f"{role}_pid"] for row in rows}) != 1 for role in role_pids):
        raise ValueError("a service role has more than one released PID")
    validate_complete(rows, scenarios, role_pids)

    attacks = [row for row in rows if row["scenario_type"] == "attack"]
    controls = [row for row in rows if row["scenario_type"] == "benign"]
    receipt_attacks = [
        row for row in attacks if row["policy"] == "receipt-bound"
    ]
    stale_attacks = [row for row in attacks if row["policy"] != "receipt-bound"]
    integrity = [
        {
            "rows": len(rows),
            "unique_keys": len({(row["policy"], row["scenario_id"]) for row in rows}),
            "policies": len({row["policy"] for row in rows}),
            "scenario_ids": len({row["scenario_id"] for row in rows}),
            "service_pids": len(set(role_pids.values())),
            "attack_rows": len(attacks),
            "causal_active_rows": sum(row["precommit_mutation_active"] for row in attacks),
            "stale_attack_commits": sum(row["attack"] for row in stale_attacks),
            "receipt_attack_commits": sum(row["attack"] for row in receipt_attacks),
            "control_rows": len(controls),
            "control_tasks": sum(row["task"] for row in controls),
            "duplicate_scheduled_rows": sum(row["duplicate_delivery"] for row in rows),
            "duplicate_delivered_rows": sum(row["delivery_attempts"] == 2 for row in rows),
            "delivery_attempts": sum(row["delivery_attempts"] for row in rows),
            "ledger_rows": sum(row["ledger_rows"] for row in rows),
        }
    ]
    expected = {
        "rows": 600,
        "unique_keys": 600,
        "policies": len(POLICIES),
        "scenario_ids": 150,
        "service_pids": 3,
        "attack_rows": 400,
        "causal_active_rows": 400,
        "stale_attack_commits": 300,
        "receipt_attack_commits": 0,
        "control_rows": 200,
        "control_tasks": 200,
        "duplicate_scheduled_rows": 120,
        "duplicate_delivered_rows": 100,
        "delivery_attempts": 600,
        "ledger_rows": 500,
    }
    if integrity[0] != expected:
        raise ValueError(f"integrity mismatch: {integrity[0]}")

    write_csv(pathlib.Path(f"{args.output_prefix}_summary.csv"), summarize(rows))
    write_csv(pathlib.Path(f"{args.output_prefix}_paired.csv"), paired(rows))
    write_csv(pathlib.Path(f"{args.output_prefix}_integrity.csv"), integrity)
    print(
        "multiprocess audit passed: rows=600 attacks=400 controls=200 "
        "stale_invalid_commits=300 receipt_invalid_commits=0"
    )


if __name__ == "__main__":
    main()
