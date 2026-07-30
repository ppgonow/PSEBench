#!/usr/bin/env python3
"""Reconstruct the asynchronous queue result without broker or effect services."""

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


POLICIES = ("check-once", "receipt-bound")
PROFILES = ("steady-consumer", "broker-restart")
INTEGER_FIELDS = {
    "attack",
    "task",
    "committed",
    "external_verify_allow",
    "enqueue_sequence",
    "enqueue_before_mutation_gate",
    "mutation_before_delivery_gate",
    "substitution_gate",
    "restart_profile",
    "broker_restart_gate",
    "fifo_gate",
    "duplicate_delivery",
    "queue_delivery_attempts",
    "queue_release_rows",
    "queue_ack_rows",
    "queue_final_acked",
    "effect_delivery_attempts",
    "effect_rows",
    "nonce_rows",
    "second_idempotent",
    "distinct_roles",
}


def read_detail(path: pathlib.Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows: list[dict[str, Any]] = list(csv.DictReader(handle))
    for row in rows:
        for field in INTEGER_FIELDS:
            row[field] = int(row[field])
        row["consumer_us"] = float(row["consumer_us"])
    return rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["profile"], row["policy"])].append(row)
    output: list[dict[str, Any]] = []
    for (profile, policy), selected in sorted(groups.items()):
        attacks = [row for row in selected if row["scenario_type"] == "attack"]
        controls = [row for row in selected if row["scenario_type"] == "benign"]
        output.append(
            {
                "profile": profile,
                "policy": policy,
                "rows": len(selected),
                "attack_n": len(attacks),
                "stale_commits": sum(row["attack"] for row in attacks),
                "control_n": len(controls),
                "control_tasks": sum(row["task"] for row in controls),
                "duplicate_rows": sum(row["duplicate_delivery"] for row in selected),
                "queue_deliveries": sum(
                    row["queue_delivery_attempts"] for row in selected
                ),
                "effect_attempts": sum(
                    row["effect_delivery_attempts"] for row in selected
                ),
                "effect_rows": sum(row["effect_rows"] for row in selected),
                "nonce_rows": sum(row["nonce_rows"] for row in selected),
            }
        )
    return output


def integrity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    attacks = [row for row in rows if row["scenario_type"] == "attack"]
    restart_rows = [row for row in rows if row["restart_profile"]]
    return [
        {
            "rows": len(rows),
            "unique_keys": len(
                {(row["profile"], row["policy"], row["scenario_id"]) for row in rows}
            ),
            "attack_rows": len(attacks),
            "control_rows": len(rows) - len(attacks),
            "stale_commits": sum(row["attack"] for row in attacks),
            "control_tasks": sum(row["task"] for row in rows),
            "attack_enqueue_gates": sum(
                row["enqueue_before_mutation_gate"] for row in attacks
            ),
            "attack_delivery_gates": sum(
                row["mutation_before_delivery_gate"] for row in attacks
            ),
            "substitution_rows": sum(row["substitution_gate"] for row in rows),
            "restart_rows": len(restart_rows),
            "restart_gates": sum(row["broker_restart_gate"] for row in restart_rows),
            "fifo_gates": sum(row["fifo_gate"] for row in rows),
            "duplicate_rows": sum(row["duplicate_delivery"] for row in rows),
            "queue_deliveries": sum(
                row["queue_delivery_attempts"] for row in rows
            ),
            "queue_releases": sum(row["queue_release_rows"] for row in rows),
            "queue_acks": sum(row["queue_ack_rows"] for row in rows),
            "queue_final_acked": sum(row["queue_final_acked"] for row in rows),
            "effect_attempts": sum(
                row["effect_delivery_attempts"] for row in rows
            ),
            "effect_rows": sum(row["effect_rows"] for row in rows),
            "nonce_rows": sum(row["nonce_rows"] for row in rows),
            "second_idempotent_rows": sum(
                row["second_idempotent"] for row in rows
            ),
            "distinct_role_rows": sum(row["distinct_roles"] for row in rows),
        }
    ]


def validate(rows: list[dict[str, Any]], scenario_dir: pathlib.Path) -> None:
    scenarios = load_scenarios(scenario_dir)
    expected = {
        (profile, policy, str(scenario["id"]))
        for profile in PROFILES
        for policy in POLICIES
        for scenario in scenarios
    }
    observed = {
        (row["profile"], row["policy"], row["scenario_id"]) for row in rows
    }
    if len(rows) != 600 or observed != expected:
        raise ValueError("detail does not contain the frozen 600-row async matrix")
    for row in rows:
        attack = row["scenario_type"] == "attack"
        receipt_bound = row["policy"] == "receipt-bound"
        duplicate = bool(row["duplicate_delivery"])
        expected_effect = not (receipt_bound and attack)
        expected_attempts = 2 if duplicate else 1
        expected_nonce = int(
            receipt_bound and expected_effect and row["family"] == "confirmation-replay"
        )
        expected_substitution = int(attack and row["family"] == "effect-substitution")
        expected_restart = int(row["profile"] == "broker-restart")
        invariant = (
            row["attack"] == int(attack and not receipt_bound)
            and row["task"] == int(not attack and expected_effect)
            and row["committed"] == int(expected_effect)
            and row["external_verify_allow"] == 1
            and row["enqueue_before_mutation_gate"] == int(attack)
            and row["mutation_before_delivery_gate"] == int(attack)
            and row["substitution_gate"] == expected_substitution
            and row["restart_profile"] == expected_restart
            and row["broker_restart_gate"] == expected_restart
            and row["fifo_gate"] == 1
            and row["queue_delivery_attempts"] == expected_attempts
            and row["queue_release_rows"] == int(duplicate)
            and row["queue_ack_rows"] == 1
            and row["queue_final_acked"] == 1
            and row["effect_delivery_attempts"] == expected_attempts
            and row["effect_rows"] == int(expected_effect)
            and row["nonce_rows"] == expected_nonce
            and row["second_idempotent"] == int(duplicate and expected_effect)
            and row["distinct_roles"] == 1
        )
        if not invariant:
            raise ValueError(f"async queue row invariant failed: {row}")
    frozen = {
        "rows": 600,
        "unique_keys": 600,
        "attack_rows": 400,
        "control_rows": 200,
        "stale_commits": 200,
        "control_tasks": 200,
        "attack_enqueue_gates": 400,
        "attack_delivery_gates": 400,
        "substitution_rows": 80,
        "restart_rows": 300,
        "restart_gates": 300,
        "fifo_gates": 600,
        "duplicate_rows": 120,
        "queue_deliveries": 720,
        "queue_releases": 120,
        "queue_acks": 600,
        "queue_final_acked": 600,
        "effect_attempts": 720,
        "effect_rows": 400,
        "nonce_rows": 20,
        "second_idempotent_rows": 80,
        "distinct_role_rows": 600,
    }
    observed_integrity = integrity(rows)[0]
    if observed_integrity != frozen:
        raise ValueError(f"async queue integrity mismatch: {observed_integrity}")


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
        default=ROOT / "analysis" / "async_queue_commit_detail.csv",
    )
    parser.add_argument(
        "--scenario-dir",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument(
        "--output-prefix",
        type=pathlib.Path,
        default=ROOT / "tmp" / "async_queue_commit_audit",
    )
    args = parser.parse_args()
    rows = read_detail(args.detail)
    validate(rows, args.scenario_dir)
    write_csv(pathlib.Path(f"{args.output_prefix}_summary.csv"), summarize(rows))
    write_csv(pathlib.Path(f"{args.output_prefix}_integrity.csv"), integrity(rows))
    print(
        "async queue audit passed: rows=600 stale_check_once=200 "
        "stale_receipt_bound=0 restart_gates=300"
    )


if __name__ == "__main__":
    main()
