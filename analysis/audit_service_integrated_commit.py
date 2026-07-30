#!/usr/bin/env python3
"""Reconstruct the service-integrated atomic-commit result without services."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from run_http_commit_race import load_scenarios  # noqa: E402


POLICIES = ("gateway-split", "service-atomic")
CRITICAL_FAMILIES = (
    "authorization-revocation",
    "confirmation-replay",
    "lease-expiry",
    "principal-switch",
)
INTEGER_FIELDS = {
    "attack",
    "task",
    "committed",
    "valid_at_linearization",
    "authorized_attack_commit",
    "external_verify_allow",
    "mutation_applied_before_request",
    "verifier_gate",
    "mutation_requested_after_verify",
    "mutation_deferred_at_gate",
    "serialized_commit_before_mutation",
    "duplicate_delivery",
    "delivery_attempts",
    "effect_rows",
    "nonce_rows",
    "second_idempotent",
    "role_distinct",
}


def read_detail(path: pathlib.Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows: list[dict[str, Any]] = list(csv.DictReader(handle))
    for row in rows:
        for field in INTEGER_FIELDS:
            row[field] = int(row[field])
        row["client_us"] = float(row["client_us"])
    return rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["schedule"]), str(row["policy"]))].append(row)
    output: list[dict[str, Any]] = []
    for (schedule, policy), selected in sorted(groups.items()):
        attacks = [row for row in selected if row["scenario_type"] == "attack"]
        controls = [row for row in selected if row["scenario_type"] == "benign"]
        output.append(
            {
                "schedule": schedule,
                "policy": policy,
                "rows": len(selected),
                "attack_n": len(attacks),
                "stale_commits": sum(row["attack"] for row in attacks),
                "control_n": len(controls),
                "control_tasks": sum(row["task"] for row in controls),
                "authorized_attack_commits": sum(
                    row["authorized_attack_commit"] for row in attacks
                ),
                "delivery_attempts": sum(row["delivery_attempts"] for row in selected),
                "effect_rows": sum(row["effect_rows"] for row in selected),
                "nonce_rows": sum(row["nonce_rows"] for row in selected),
            }
        )
    return output


def integrity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    attacks = [row for row in rows if row["scenario_type"] == "attack"]
    controls = [row for row in rows if row["scenario_type"] == "benign"]
    critical_atomic = [
        row
        for row in attacks
        if row["schedule"] == "critical-window" and row["policy"] == "service-atomic"
    ]
    return [
        {
            "rows": len(rows),
            "unique_keys": len(
                {(row["schedule"], row["policy"], row["scenario_id"]) for row in rows}
            ),
            "attack_rows": len(attacks),
            "control_rows": len(controls),
            "stale_commits": sum(row["attack"] for row in attacks),
            "control_tasks": sum(row["task"] for row in controls),
            "critical_atomic_rows": len(critical_atomic),
            "critical_verifier_gates": sum(row["verifier_gate"] for row in critical_atomic),
            "critical_mutation_request_gates": sum(
                row["mutation_requested_after_verify"] for row in critical_atomic
            ),
            "critical_deferred_lock_gates": sum(
                row["mutation_deferred_at_gate"] for row in critical_atomic
            ),
            "critical_serialized_commits": sum(
                row["serialized_commit_before_mutation"] for row in critical_atomic
            ),
            "duplicate_rows": sum(row["duplicate_delivery"] for row in rows),
            "delivery_attempts": sum(row["delivery_attempts"] for row in rows),
            "effect_rows": sum(row["effect_rows"] for row in rows),
            "nonce_rows": sum(row["nonce_rows"] for row in rows),
            "distinct_service_role_rows": sum(row["role_distinct"] for row in rows),
        }
    ]


def validate(rows: list[dict[str, Any]], scenario_dir: pathlib.Path) -> None:
    scenarios = load_scenarios(scenario_dir)
    pre_ids = {str(scenario["id"]) for scenario in scenarios}
    critical_ids = {
        str(scenario["id"])
        for scenario in scenarios
        if scenario["family"] in CRITICAL_FAMILIES
    }
    expected = {
        *(('pre-transaction', policy, scenario_id) for policy in POLICIES for scenario_id in pre_ids),
        *(('critical-window', policy, scenario_id) for policy in POLICIES for scenario_id in critical_ids),
    }
    observed = {
        (row["schedule"], row["policy"], row["scenario_id"]) for row in rows
    }
    if len(rows) != 540 or observed != expected:
        raise ValueError("detail does not contain the frozen 540-row matrix")
    for row in rows:
        attack = row["scenario_type"] == "attack"
        atomic = row["policy"] == "service-atomic"
        critical = row["schedule"] == "critical-window"
        expected_effect = not (atomic and not critical and attack)
        expected_stale = attack and not atomic
        expected_attempts = 2 if row["duplicate_delivery"] else 1
        expected_nonce = int(
            atomic and expected_effect and row["family"] == "confirmation-replay"
        )
        invariant = (
            row["committed"] == int(expected_effect)
            and row["effect_rows"] == int(expected_effect)
            and row["attack"] == int(expected_stale)
            and row["task"] == int(not attack and expected_effect)
            and row["delivery_attempts"] == expected_attempts
            and row["nonce_rows"] == expected_nonce
            and row["external_verify_allow"] == 1
            and row["role_distinct"] == 1
            and (not row["duplicate_delivery"] or not expected_effect or row["second_idempotent"] == 1)
            and (not row["duplicate_delivery"] or expected_effect or row["second_idempotent"] == 0)
            and (not attack or critical or row["mutation_applied_before_request"] == 1)
            and (
                not (attack and critical and not atomic)
                or row["mutation_applied_before_request"] == 1
            )
            and (
                not (attack and critical and atomic)
                or (
                    row["verifier_gate"] == 1
                    and row["mutation_requested_after_verify"] == 1
                    and row["mutation_deferred_at_gate"] == 1
                    and row["serialized_commit_before_mutation"] == 1
                    and row["authorized_attack_commit"] == 1
                )
            )
        )
        if not invariant:
            raise ValueError(f"row invariant failed: {row}")
    frozen = {
        "rows": 540,
        "unique_keys": 540,
        "attack_rows": 360,
        "control_rows": 180,
        "stale_commits": 180,
        "control_tasks": 180,
        "critical_atomic_rows": 80,
        "critical_verifier_gates": 80,
        "critical_mutation_request_gates": 80,
        "critical_deferred_lock_gates": 80,
        "critical_serialized_commits": 80,
        "duplicate_rows": 108,
        "delivery_attempts": 648,
        "effect_rows": 440,
        "nonce_rows": 40,
        "distinct_service_role_rows": 540,
    }
    observed_integrity = integrity(rows)[0]
    if observed_integrity != frozen:
        raise ValueError(f"integrity mismatch: {observed_integrity}")


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--detail",
        type=pathlib.Path,
        default=ROOT / "analysis" / "service_integrated_commit_detail.csv",
    )
    parser.add_argument(
        "--scenario-dir",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument(
        "--output-prefix",
        type=pathlib.Path,
        default=ROOT / "tmp" / "service_integrated_commit_audit",
    )
    args = parser.parse_args()
    rows = read_detail(args.detail)
    validate(rows, args.scenario_dir)
    write_csv(pathlib.Path(f"{args.output_prefix}_summary.csv"), summarize(rows))
    write_csv(pathlib.Path(f"{args.output_prefix}_integrity.csv"), integrity(rows))
    print(
        "service-integrated audit passed: rows=540 stale_split=180 "
        "stale_atomic=0 critical_serialized=80"
    )


if __name__ == "__main__":
    main()
