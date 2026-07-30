#!/usr/bin/env python3
"""Independently audit the released Docker-isolated commit-race tables."""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from run_container_commit_race import validate_container_complete  # noqa: E402
from run_http_commit_race import load_scenarios  # noqa: E402
from run_multiprocess_commit_race import POLICIES, paired, summarize, write_csv  # noqa: E402


DETAIL_INTEGER_FIELDS = {
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
    "authorization_instance_id",
    "gateway_instance_id",
    "effect_instance_id",
}
DETAIL_FLOAT_FIELDS = {"auth_query_us", "service_call_us", "gateway_total_us"}
TOPOLOGY_INTEGER_FIELDS = {
    "service_instance_id",
    "network_internal",
    "network_count",
    "published_binding_count",
    "read_only_rootfs",
    "cap_drop_all",
    "no_new_privileges",
    "nonroot_user",
    "running",
}


def read_csv(
    path: pathlib.Path,
    integer_fields: set[str],
    float_fields: set[str] | None = None,
) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows: list[dict[str, Any]] = list(csv.DictReader(handle))
    for row in rows:
        for field in integer_fields:
            row[field] = int(row[field])
        for field in float_fields or set():
            row[field] = float(row[field])
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--detail",
        type=pathlib.Path,
        default=ROOT / "analysis" / "container_commit_race_detail.csv",
    )
    parser.add_argument(
        "--topology",
        type=pathlib.Path,
        default=ROOT / "analysis" / "container_commit_race_topology.csv",
    )
    parser.add_argument(
        "--scenario-dir",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument(
        "--output-prefix",
        type=pathlib.Path,
        default=ROOT / "tmp" / "container_commit_race_audit",
    )
    args = parser.parse_args()

    rows = read_csv(args.detail, DETAIL_INTEGER_FIELDS, DETAIL_FLOAT_FIELDS)
    topology = read_csv(args.topology, TOPOLOGY_INTEGER_FIELDS)
    scenarios = load_scenarios(args.scenario_dir)
    validate_container_complete(rows, scenarios, topology)

    attacks = [row for row in rows if row["scenario_type"] == "attack"]
    controls = [row for row in rows if row["scenario_type"] == "benign"]
    stale_attacks = [row for row in attacks if row["policy"] != "receipt-bound"]
    receipt_attacks = [row for row in attacks if row["policy"] == "receipt-bound"]
    integrity = [
        {
            "rows": len(rows),
            "unique_keys": len({(row["policy"], row["scenario_id"]) for row in rows}),
            "policies": len({row["policy"] for row in rows}),
            "scenario_ids": len({row["scenario_id"] for row in rows}),
            "container_hashes": len({row["container_id_sha256"] for row in topology}),
            "namespace_hashes": len(
                {row["network_namespace_sha256"] for row in topology}
            ),
            "container_ips": len({row["ip_address"] for row in topology}),
            "shared_network_hashes": len({row["network_id_sha256"] for row in topology}),
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
        "container_hashes": 3,
        "namespace_hashes": 3,
        "container_ips": 3,
        "shared_network_hashes": 1,
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
        "container audit passed: rows=600 attacks=400 controls=200 "
        "stale_invalid_commits=300 receipt_invalid_commits=0"
    )


if __name__ == "__main__":
    main()
