#!/usr/bin/env python3
"""Independently audit the frozen native service-commit bridge artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
ALIASES = ("gpt-5.5", "grok-4.5", "gpt-5.4", "gpt-5.6-sol")
POLICIES = ("cached-pre-action", "receipt-bound")
STATES = ("stable", "revoked")


def read_csv(path: pathlib.Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def exact_p(b: int, c: int) -> float:
    discordant = b + c
    if discordant == 0:
        return 1.0
    lower = min(b, c)
    tail = sum(math.comb(discordant, value) for value in range(lower + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def audit_files(
    attempts_path: pathlib.Path,
    raw_path: pathlib.Path,
    detail_path: pathlib.Path,
    summary_path: pathlib.Path,
    paired_path: pathlib.Path,
    integrity_path: pathlib.Path,
    topology_path: pathlib.Path,
) -> list[dict[str, Any]]:
    attempts = [
        json.loads(line) for line in attempts_path.read_text(encoding="utf-8").splitlines()
    ]
    raw = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    detail = read_csv(detail_path)
    summary = read_csv(summary_path)
    paired = read_csv(paired_path)
    integrity = read_csv(integrity_path)
    topology = read_csv(topology_path)
    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, observed: Any, expected: Any) -> None:
        checks.append(
            {
                "check": name,
                "passed": int(passed),
                "observed": observed,
                "expected": expected,
            }
        )

    raw_keys = {
        (row["requested_alias"], row["scenario_id"], row["policy"], row["state"])
        for row in raw
    }
    attempt_keys = {
        (row["requested_alias"], row["scenario_id"], row["policy"], row["state"])
        for row in attempts
    }
    detail_keys = {
        (row["requested_alias"], row["scenario_id"], row["policy"], row["state"])
        for row in detail
    }
    record("raw_rows", len(raw) == 768, len(raw), 768)
    record("attempt_rows", len(attempts) == 768, len(attempts), 768)
    record(
        "attempt_status",
        all(row.get("status") == "complete" for row in attempts),
        sum(row.get("status") == "complete" for row in attempts),
        768,
    )
    record("detail_rows", len(detail) == 768, len(detail), 768)
    record("unique_raw_keys", len(raw_keys) == 768, len(raw_keys), 768)
    record("raw_detail_keys", raw_keys == detail_keys, len(raw_keys & detail_keys), 768)
    record("attempt_raw_keys", attempt_keys == raw_keys, len(attempt_keys & raw_keys), 768)

    native_keys = {(row["requested_alias"], row["scenario_id"]) for row in raw}
    record("native_proposals", len(native_keys) == 192, len(native_keys), 192)
    for alias in ALIASES:
        alias_rows = [row for row in raw if row["requested_alias"] == alias]
        alias_proposals = {row["scenario_id"] for row in alias_rows}
        record(f"{alias}:rows", len(alias_rows) == 192, len(alias_rows), 192)
        record(f"{alias}:proposals", len(alias_proposals) == 48, len(alias_proposals), 48)
        for policy in POLICIES:
            for state in STATES:
                selected = [
                    row
                    for row in alias_rows
                    if row["policy"] == policy and row["state"] == state
                ]
                expected_commits = 48 if state == "stable" or policy == "cached-pre-action" else 0
                observed_commits = sum(int(row["committed"]) for row in selected)
                record(
                    f"{alias}:{policy}:{state}:n",
                    len(selected) == 48,
                    len(selected),
                    48,
                )
                record(
                    f"{alias}:{policy}:{state}:commits",
                    observed_commits == expected_commits,
                    observed_commits,
                    expected_commits,
                )

    revoked = [row for row in raw if row["state"] == "revoked"]
    stable = [row for row in raw if row["state"] == "stable"]
    for field in (
        "mutation_observed_active",
        "mutation_active_precommit",
        "commit_after_mutation_observation",
        "mutation_completed",
    ):
        observed = sum(int(row[field]) for row in revoked)
        record(f"revoked:{field}", observed == 384, observed, 384)
    record(
        "frozen_timing",
        all(
            float(row["configured_commit_delay_ms"]) == 10.0
            and float(row["configured_mutation_hold_ms"]) == 1000.0
            for row in raw
        ),
        sum(
            float(row["configured_commit_delay_ms"]) == 10.0
            and float(row["configured_mutation_hold_ms"]) == 1000.0
            for row in raw
        ),
        768,
    )
    record(
        "stable_no_mutation_gates",
        all(
            int(row["mutation_observed_active"]) == 0
            and int(row["mutation_active_precommit"]) == 0
            and int(row["commit_after_mutation_observation"]) == 0
            for row in stable
        ),
        sum(int(row["mutation_observed_active"]) for row in stable),
        0,
    )
    for field in ("transport_hash_match", "ledger_hash_match", "role_chain_verified"):
        observed = sum(int(row[field]) for row in raw)
        record(field, observed == 768, observed, 768)
    record(
        "ledger_cardinality",
        all(int(row["effect_rows"]) == int(row["committed"]) for row in raw),
        sum(int(row["effect_rows"]) for row in raw),
        576,
    )
    record(
        "one_delivery_per_trial",
        all(int(row["delivery_attempts"]) == 1 for row in raw),
        sum(int(row["delivery_attempts"]) for row in raw),
        768,
    )

    summary_index = {
        (row["requested_alias"], row["policy"], row["state"]): row for row in summary
    }
    record("summary_cells", len(summary_index) == 16, len(summary_index), 16)
    summary_recomputed = True
    for key, cell in summary_index.items():
        selected = [
            row
            for row in raw
            if (row["requested_alias"], row["policy"], row["state"]) == key
        ]
        summary_recomputed &= int(cell["n"]) == len(selected)
        summary_recomputed &= int(cell["commits"]) == sum(
            int(row["committed"]) for row in selected
        )
        summary_recomputed &= int(cell["stale_commits"]) == sum(
            int(row["stale_commit"]) for row in selected
        )
    record("summary_recomputed", summary_recomputed, int(summary_recomputed), 1)

    paired_index = {row["requested_alias"]: row for row in paired}
    record("paired_aliases", set(paired_index) == set(ALIASES), len(paired_index), 4)
    paired_recomputed = True
    for alias in ALIASES:
        row = paired_index.get(alias, {})
        paired_recomputed &= int(row.get("n_pairs", -1)) == 48
        paired_recomputed &= int(row.get("cached_yes_receipt_no", -1)) == 48
        paired_recomputed &= int(row.get("cached_no_receipt_yes", -1)) == 0
        paired_recomputed &= math.isclose(
            float(row.get("exact_mcnemar_p", "nan")), exact_p(48, 0), rel_tol=1e-12
        )
    record("paired_recomputed", paired_recomputed, int(paired_recomputed), 1)

    integrity_ok = len(integrity) == 1
    if integrity_ok:
        item = integrity[0]
        expected_integrity = {
            "rows": 768,
            "unique_keys": 768,
            "aliases": 4,
            "unique_native_proposals": 192,
            "stable_rows": 384,
            "revoked_rows": 384,
            "revoked_mutation_observed_active": 384,
            "revoked_mutation_active_precommit": 384,
            "revoked_commit_after_observation": 384,
            "transport_hash_matches": 768,
            "ledger_hash_matches": 768,
            "role_chain_verified": 768,
            "stable_cached_commits": 192,
            "stable_receipt_commits": 192,
            "revoked_cached_stale_commits": 192,
            "revoked_receipt_stale_commits": 0,
            "effect_rows": 576,
            "delivery_attempts": 768,
            "ephemeral_cleanup_verified": 1,
        }
        integrity_ok = all(int(item[field]) == expected for field, expected in expected_integrity.items())
    record("integrity_totals", integrity_ok, int(integrity_ok), 1)

    topology_ok = len(topology) == 1
    if topology_ok:
        item = topology[0]
        topology_ok = all(
            int(item[field]) == expected
            for field, expected in {
                "process_count": 3,
                "distinct_processes": 1,
                "loopback_only": 1,
                "health_gate": 1,
                "authorization_effect_relay_gate": 1,
                "gateway_effect_relay_gate": 1,
                "unique_identity_commitments": 1,
            }.items()
        )
        commitments = {
            item["authorization_identity_sha256"],
            item["gateway_identity_sha256"],
            item["effect_identity_sha256"],
        }
        topology_ok &= len(commitments) == 3 and all(
            len(value) == 64 and set(value) <= set("0123456789abcdef")
            for value in commitments
        )
    record("anonymous_topology", topology_ok, int(topology_ok), 1)
    return checks


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--raw",
        type=pathlib.Path,
        default=ROOT / "results" / "native_service_commit_bridge" / "native_service_commit_bridge.jsonl",
    )
    parser.add_argument(
        "--analysis-prefix",
        type=pathlib.Path,
        default=ROOT / "analysis" / "native_service_commit_bridge",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=ROOT / "analysis" / "native_service_commit_bridge_audit.csv",
    )
    args = parser.parse_args()
    checks = audit_files(
        args.raw.parent / "native_service_commit_bridge_attempts.jsonl",
        args.raw,
        pathlib.Path(f"{args.analysis_prefix}_detail.csv"),
        pathlib.Path(f"{args.analysis_prefix}_summary.csv"),
        pathlib.Path(f"{args.analysis_prefix}_paired.csv"),
        pathlib.Path(f"{args.analysis_prefix}_integrity.csv"),
        pathlib.Path(f"{args.analysis_prefix}_topology.csv"),
    )
    write_csv(args.output, checks)
    failed = [row["check"] for row in checks if not row["passed"]]
    if failed:
        raise SystemExit(f"native service bridge audit failed: {failed}")
    print(f"native service bridge audit passed: {len(checks)} checks")


if __name__ == "__main__":
    main()
