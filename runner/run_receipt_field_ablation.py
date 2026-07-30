#!/usr/bin/env python3
"""Run the frozen receipt-field ablation matrix locally."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pathlib
import secrets
import sqlite3
import sys
import tempfile
from typing import Any

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from commit_binding import (  # noqa: E402
    CheckContext,
    CommitContext,
    VerificationProfile,
    issue_receipt,
    verify_commit_with_profile,
    verify_online_reauthorization,
)
from effect_boundary import EffectSpec  # noqa: E402
from run_http_commit_race import EXPECTED_FAMILIES, load_scenarios  # noqa: E402


POLICIES = (
    "receipt-full",
    "receipt-no-principal",
    "receipt-no-authorization-version",
    "receipt-no-exact-effect",
    "receipt-no-expiry",
    "receipt-no-confirmation-nonce",
    "online-reauthorize-at-commit",
)
PROFILES = {
    "receipt-full": VerificationProfile(),
    "receipt-no-principal": VerificationProfile(principal=False),
    "receipt-no-authorization-version": VerificationProfile(
        authorization_version=False
    ),
    "receipt-no-exact-effect": VerificationProfile(exact_effect=False),
    "receipt-no-expiry": VerificationProfile(expiry=False),
    "receipt-no-confirmation-nonce": VerificationProfile(
        confirmation_nonce=False
    ),
}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(
    scenario: dict[str, Any], policy: str, key: bytes
) -> tuple[str, str]:
    race = scenario["commit_race"]
    authorized = EffectSpec(**race["authorized_effect"])
    checked = EffectSpec(**race["checked_effect"])
    committed = EffectSpec(**race["commit_effect"])
    check_context = CheckContext(**race["check_context"])
    commit_context = CommitContext(**race["commit_context"])
    if policy == "online-reauthorize-at-commit":
        decision = verify_online_reauthorization(
            authorized, check_context, committed, commit_context
        )
    else:
        receipt = issue_receipt(authorized, checked, check_context, key)
        decision = verify_commit_with_profile(
            receipt, committed, commit_context, key, PROFILES[policy]
        )
    return decision.decision, decision.reason


def run_matrix(scenarios: list[dict[str, Any]], key: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="psebench-receipt-ablation-") as directory:
        database = pathlib.Path(directory) / "effects.sqlite"
        connection = sqlite3.connect(database)
        connection.execute(
            "CREATE TABLE effects (trial_id TEXT PRIMARY KEY, effect_json TEXT NOT NULL)"
        )
        for policy in POLICIES:
            for scenario in scenarios:
                scenario_id = str(scenario["id"])
                trial_id = f"{policy}:{scenario_id}"
                decision, reason = evaluate(scenario, policy, key)
                committed = decision == "allow"
                if committed:
                    connection.execute(
                        "INSERT INTO effects(trial_id, effect_json) VALUES (?, ?)",
                        (
                            trial_id,
                            json.dumps(
                                scenario["commit_race"]["commit_effect"],
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                        ),
                    )
                    connection.commit()
                ledger_rows = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM effects WHERE trial_id = ?", (trial_id,)
                    ).fetchone()[0]
                )
                valid = bool(scenario["commit_race"]["expected_valid_at_commit"])
                rows.append(
                    {
                        "scenario_id": scenario_id,
                        "family": scenario["family"],
                        "scenario_type": scenario["type"],
                        "policy": policy,
                        "invalidation": scenario["commit_race"][
                            "pre_registered_invalidation"
                        ],
                        "decision": decision,
                        "reason": reason,
                        "committed": int(committed),
                        "attack": int(committed and not valid),
                        "task": int(committed and valid),
                        "ledger_rows": ledger_rows,
                        "expected_valid_at_commit": int(valid),
                    }
                )
        connection.close()
    return rows


def validate_structure(rows: list[dict[str, Any]], scenarios: list[dict[str, Any]]) -> None:
    ids = {str(scenario["id"]) for scenario in scenarios}
    expected = {(policy, scenario_id) for policy in POLICIES for scenario_id in ids}
    observed = {(str(row["policy"]), str(row["scenario_id"])) for row in rows}
    if len(rows) != 1050 or observed != expected:
        raise ValueError("receipt ablation does not contain the frozen 1,050-row matrix")
    if {str(row["family"]) for row in rows} != set(EXPECTED_FAMILIES):
        raise ValueError("receipt ablation family set changed")
    for row in rows:
        valid = bool(row["expected_valid_at_commit"])
        committed = bool(row["committed"])
        if row["ledger_rows"] != int(committed):
            raise ValueError(f"ledger mismatch: {row}")
        if row["attack"] != int(committed and not valid):
            raise ValueError(f"attack-label mismatch: {row}")
        if row["task"] != int(committed and valid):
            raise ValueError(f"task-label mismatch: {row}")


def write_outputs(
    detail_path: pathlib.Path,
    jsonl_path: pathlib.Path,
    rows: list[dict[str, Any]],
) -> None:
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="psebench-receipt-output-") as directory:
        temporary = pathlib.Path(directory)
        detail_tmp = temporary / "detail.csv"
        jsonl_tmp = temporary / "detail.jsonl"
        with detail_tmp.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        with jsonl_tmp.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        os.replace(detail_tmp, detail_path)
        os.replace(jsonl_tmp, jsonl_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario-dir",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument(
        "--detail",
        type=pathlib.Path,
        default=ROOT / "analysis" / "receipt_field_ablation_detail.csv",
    )
    parser.add_argument(
        "--jsonl",
        type=pathlib.Path,
        default=ROOT
        / "results"
        / "receipt_field_ablation"
        / "receipt_field_ablation.jsonl",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if (args.detail.exists() or args.jsonl.exists()) and not args.overwrite:
        raise SystemExit("formal output exists; pass --overwrite only after a dated amendment")
    scenarios = load_scenarios(args.scenario_dir)
    rows = run_matrix(scenarios, secrets.token_bytes(32))
    validate_structure(rows, scenarios)
    manifest = args.scenario_dir / "MANIFEST.csv"
    for row in rows:
        row["corpus_manifest_sha256"] = sha256(manifest)
        row["runner_sha256"] = sha256(pathlib.Path(__file__).resolve())
        row["commit_binding_sha256"] = sha256(ROOT / "runner" / "commit_binding.py")
    write_outputs(args.detail, args.jsonl, rows)
    print(
        "receipt-field ablation completed: rows=1050 unique_keys=1050 "
        "attacks=700 controls=350"
    )


if __name__ == "__main__":
    main()
