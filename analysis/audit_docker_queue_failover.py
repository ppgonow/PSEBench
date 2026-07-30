#!/usr/bin/env python3
"""Audit Docker queue failover results without Docker or services."""

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


PROFILES = ("partition-before-commit", "crash-after-commit")
POLICIES = ("check-once", "receipt-bound")
IMAGE_DIGEST = "sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de"
INTEGER_FIELDS = {
    "attack",
    "task",
    "committed",
    "external_verify_allow",
    "substitution_gate",
    "consumer_a_claim_gate",
    "partition_gate",
    "partition_failure_gate",
    "crash_commit_gate",
    "consumer_killed_gate",
    "recovery_gate",
    "consumer_b_gate",
    "queue_delivery_attempts",
    "queue_recovery_rows",
    "queue_ack_rows",
    "queue_final_acked",
    "effect_delivery_attempts",
    "effect_rows",
    "nonce_rows",
    "second_idempotent",
    "distinct_role_gate",
    "loopback_publish_gate",
    "bridge_gate",
}


def read_csv(path: pathlib.Path, *, integers: bool = False) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows: list[dict[str, Any]] = list(csv.DictReader(handle))
    if integers:
        for row in rows:
            for field in INTEGER_FIELDS:
                row[field] = int(row[field])
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
                "queue_deliveries": sum(row["queue_delivery_attempts"] for row in selected),
                "effect_attempts": sum(row["effect_delivery_attempts"] for row in selected),
                "effect_rows": sum(row["effect_rows"] for row in selected),
            }
        )
    return output


def integrity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    attacks = [row for row in rows if row["scenario_type"] == "attack"]
    return [
        {
            "rows": len(rows),
            "unique_keys": len({(row["profile"], row["policy"], row["scenario_id"]) for row in rows}),
            "attack_rows": len(attacks),
            "control_rows": len(rows) - len(attacks),
            "stale_commits": sum(row["attack"] for row in attacks),
            "control_tasks": sum(row["task"] for row in rows),
            "partition_rows": sum(row["profile"] == "partition-before-commit" for row in rows),
            "partition_gates": sum(row["partition_gate"] for row in rows),
            "partition_failure_gates": sum(row["partition_failure_gate"] for row in rows),
            "crash_rows": sum(row["profile"] == "crash-after-commit" for row in rows),
            "crash_commit_gates": sum(row["crash_commit_gate"] for row in rows),
            "consumer_killed_gates": sum(row["consumer_killed_gate"] for row in rows),
            "recovery_gates": sum(row["recovery_gate"] for row in rows),
            "consumer_b_gates": sum(row["consumer_b_gate"] for row in rows),
            "substitution_rows": sum(row["substitution_gate"] for row in rows),
            "queue_deliveries": sum(row["queue_delivery_attempts"] for row in rows),
            "queue_recoveries": sum(row["queue_recovery_rows"] for row in rows),
            "queue_acks": sum(row["queue_ack_rows"] for row in rows),
            "queue_final_acked": sum(row["queue_final_acked"] for row in rows),
            "effect_attempts": sum(row["effect_delivery_attempts"] for row in rows),
            "effect_rows": sum(row["effect_rows"] for row in rows),
            "nonce_rows": sum(row["nonce_rows"] for row in rows),
            "second_idempotent_rows": sum(row["second_idempotent"] for row in rows),
            "distinct_role_rows": sum(row["distinct_role_gate"] for row in rows),
            "loopback_publish_rows": sum(row["loopback_publish_gate"] for row in rows),
            "bridge_rows": sum(row["bridge_gate"] for row in rows),
        }
    ]


def validate(
    rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    scenario_dir: pathlib.Path,
) -> None:
    scenarios = load_scenarios(scenario_dir)
    expected = {
        (profile, policy, str(scenario["id"]))
        for profile in PROFILES
        for policy in POLICIES
        for scenario in scenarios
    }
    observed = {(row["profile"], row["policy"], row["scenario_id"]) for row in rows}
    if len(rows) != 600 or observed != expected:
        raise ValueError("detail does not contain the frozen 600-row failover matrix")
    if not (
        metadata["image_digest"] == IMAGE_DIGEST
        and metadata["network_driver"] == "bridge"
        and metadata["host_publish"] == "127.0.0.1-random"
        and int(metadata["fault_epochs"]) == 4
        and int(metadata["matrix_rows"]) == 600
    ):
        raise ValueError(f"failover metadata mismatch: {metadata}")
    for row in rows:
        attack = row["scenario_type"] == "attack"
        bound = row["policy"] == "receipt-bound"
        partition = row["profile"] == "partition-before-commit"
        expected_effect = not (bound and attack)
        expected_attempts = 1 if partition else 2
        expected_nonce = int(bound and expected_effect and row["family"] == "confirmation-replay")
        expected_substitution = int(attack and row["family"] == "effect-substitution")
        invariant = (
            row["attack"] == int(attack and not bound)
            and row["task"] == int(not attack and expected_effect)
            and row["committed"] == int(expected_effect)
            and row["external_verify_allow"] == 1
            and row["substitution_gate"] == expected_substitution
            and row["consumer_a_claim_gate"] == 1
            and row["partition_gate"] == int(partition)
            and row["partition_failure_gate"] == int(partition)
            and row["crash_commit_gate"] == int(not partition)
            and row["consumer_killed_gate"] == 1
            and row["recovery_gate"] == 1
            and row["consumer_b_gate"] == 1
            and row["queue_delivery_attempts"] == 2
            and row["queue_recovery_rows"] == 1
            and row["queue_ack_rows"] == 1
            and row["queue_final_acked"] == 1
            and row["effect_delivery_attempts"] == expected_attempts
            and row["effect_rows"] == int(expected_effect)
            and row["nonce_rows"] == expected_nonce
            and row["second_idempotent"] == int(not partition and expected_effect)
            and row["distinct_role_gate"] == 1
            and row["loopback_publish_gate"] == 1
            and row["bridge_gate"] == 1
        )
        if not invariant:
            raise ValueError(f"failover row invariant failed: {row}")
    frozen = {
        "rows": 600,
        "unique_keys": 600,
        "attack_rows": 400,
        "control_rows": 200,
        "stale_commits": 200,
        "control_tasks": 200,
        "partition_rows": 300,
        "partition_gates": 300,
        "partition_failure_gates": 300,
        "crash_rows": 300,
        "crash_commit_gates": 300,
        "consumer_killed_gates": 600,
        "recovery_gates": 600,
        "consumer_b_gates": 600,
        "substitution_rows": 80,
        "queue_deliveries": 1200,
        "queue_recoveries": 600,
        "queue_acks": 600,
        "queue_final_acked": 600,
        "effect_attempts": 900,
        "effect_rows": 400,
        "nonce_rows": 20,
        "second_idempotent_rows": 200,
        "distinct_role_rows": 600,
        "loopback_publish_rows": 600,
        "bridge_rows": 600,
    }
    observed_integrity = integrity(rows)[0]
    if observed_integrity != frozen:
        raise ValueError(f"failover integrity mismatch: {observed_integrity}")


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
        default=ROOT / "analysis" / "docker_queue_failover_detail.csv",
    )
    parser.add_argument(
        "--metadata",
        type=pathlib.Path,
        default=ROOT / "analysis" / "docker_queue_failover_metadata.csv",
    )
    parser.add_argument(
        "--scenario-dir",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument(
        "--output-prefix",
        type=pathlib.Path,
        default=ROOT / "tmp" / "docker_queue_failover_audit",
    )
    args = parser.parse_args()
    rows = read_csv(args.detail, integers=True)
    metadata = read_csv(args.metadata)[0]
    validate(rows, metadata, args.scenario_dir)
    write_csv(pathlib.Path(f"{args.output_prefix}_summary.csv"), summarize(rows))
    write_csv(pathlib.Path(f"{args.output_prefix}_integrity.csv"), integrity(rows))
    print(
        "Docker queue failover audit passed: rows=600 stale_check_once=200 "
        "stale_receipt_bound=0 fault_epochs=4"
    )


if __name__ == "__main__":
    main()
