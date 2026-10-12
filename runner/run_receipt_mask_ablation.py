#!/usr/bin/env python3
"""Run the complete combinatorial receipt-verification ablation matrix.

The existing receipt experiment removes one field at a time.  This runner
enumerates every verification profile over the five receipt-bound fields so
that interactions between omissions are audited without changing the frozen
single-field corpus or its outputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import sqlite3
import sys
import tempfile
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from commit_binding import (  # noqa: E402
    CheckContext,
    CommitContext,
    VerificationProfile,
    issue_receipt,
    verify_commit_with_profile,
)
from effect_boundary import EffectSpec  # noqa: E402
from run_http_commit_race import EXPECTED_FAMILIES, load_scenarios  # noqa: E402


FIELDS = (
    "principal",
    "authorization_version",
    "exact_effect",
    "expiry",
    "confirmation_nonce",
)
FIELD_TO_FAMILY = {
    "principal": "principal-switch",
    "authorization_version": "authorization-revocation",
    "exact_effect": "effect-substitution",
    "expiry": "lease-expiry",
    "confirmation_nonce": "confirmation-replay",
}
EXPECTED_TOTAL = 32 * 150
TEST_KEY = b"psebench-receipt-mask-ablation-v1"


def profile_for_mask(mask: int) -> VerificationProfile:
    if not 0 <= mask < (1 << len(FIELDS)):
        raise ValueError(f"invalid profile mask: {mask}")
    return VerificationProfile(
        **{field: bool(mask & (1 << index)) for index, field in enumerate(FIELDS)}
    )


def mask_label(mask: int) -> str:
    disabled = [field for index, field in enumerate(FIELDS) if not (mask & (1 << index))]
    return "none" if not disabled else "+".join(disabled)


def evaluate(scenario: dict[str, Any], mask: int) -> dict[str, Any]:
    race = scenario["commit_race"]
    authorized = EffectSpec(**race["authorized_effect"])
    checked = EffectSpec(**race["checked_effect"])
    committed_effect = EffectSpec(**race["commit_effect"])
    check_context = CheckContext(**race["check_context"])
    commit_context = CommitContext(**race["commit_context"])
    receipt = issue_receipt(authorized, checked, check_context, TEST_KEY)
    decision = verify_commit_with_profile(
        receipt,
        committed_effect,
        commit_context,
        TEST_KEY,
        profile_for_mask(mask),
    )
    committed = int(decision.decision == "allow")
    valid = int(bool(race["expected_valid_at_commit"]))
    disabled = mask_label(mask)
    trial_id = f"mask:{mask:02d}:{scenario['id']}"
    return {
        "profile_mask": mask,
        "profile_hex": f"0x{mask:02x}",
        "disabled_fields": disabled,
        "scenario_id": str(scenario["id"]),
        "family": str(scenario["family"]),
        "scenario_type": str(scenario["type"]),
        "invalidation": str(race["pre_registered_invalidation"]),
        "decision": decision.decision,
        "reason": decision.reason,
        "committed": committed,
        "attack": int(committed and not valid),
        "task": int(committed and valid),
        "expected_valid_at_commit": valid,
        "ledger_trial_id": trial_id,
    }


def run_matrix(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    # The temporary ledger makes duplicate delivery visible in the same way as
    # the frozen ablation, while keeping the generated run self-contained.
    with tempfile.TemporaryDirectory(prefix="psebench-receipt-mask-") as directory:
        database = pathlib.Path(directory) / "effects.sqlite"
        connection = sqlite3.connect(database)
        connection.execute(
            "CREATE TABLE effects (trial_id TEXT PRIMARY KEY, effect_json TEXT NOT NULL)"
        )
        for mask in range(1 << len(FIELDS)):
            for scenario in scenarios:
                row = evaluate(scenario, mask)
                if row["committed"]:
                    connection.execute(
                        "INSERT INTO effects(trial_id, effect_json) VALUES (?, ?)",
                        (
                            row["ledger_trial_id"],
                            json.dumps(
                                scenario["commit_race"]["commit_effect"],
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                        ),
                    )
                    connection.commit()
                row["ledger_rows"] = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM effects WHERE trial_id = ?",
                        (row["ledger_trial_id"],),
                    ).fetchone()[0]
                )
                rows.append(row)
        connection.close()
    return rows


def validate_structure(rows: list[dict[str, Any]], scenarios: list[dict[str, Any]]) -> None:
    scenario_ids = {str(scenario["id"]) for scenario in scenarios}
    masks = set(range(1 << len(FIELDS)))
    observed = {
        (int(row["profile_mask"]), str(row["scenario_id"])) for row in rows
    }
    expected = {(mask, scenario_id) for mask in masks for scenario_id in scenario_ids}
    if len(rows) != EXPECTED_TOTAL or observed != expected:
        raise ValueError(
            f"receipt-mask matrix is incomplete: rows={len(rows)} expected={EXPECTED_TOTAL}"
        )
    if {str(row["family"]) for row in rows} != set(EXPECTED_FAMILIES):
        raise ValueError("receipt-mask family set differs from the frozen corpus")
    for row in rows:
        committed = int(row["committed"])
        valid = int(row["expected_valid_at_commit"])
        if int(row["ledger_rows"]) != committed:
            raise ValueError(f"ledger mismatch: {row}")
        if int(row["attack"]) != int(committed and not valid):
            raise ValueError(f"attack label mismatch: {row}")
        if int(row["task"]) != int(committed and valid):
            raise ValueError(f"task label mismatch: {row}")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        "--detail",
        type=pathlib.Path,
        default=ROOT / "analysis" / "receipt_mask_ablation_detail.csv",
    )
    parser.add_argument(
        "--integrity",
        type=pathlib.Path,
        default=ROOT / "analysis" / "receipt_mask_ablation_integrity.json",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.detail.exists() and not args.overwrite:
        raise SystemExit("receipt-mask output exists; pass --overwrite for a fresh run")
    scenarios = load_scenarios(args.scenario_dir)
    rows = run_matrix(scenarios)
    validate_structure(rows, scenarios)
    manifest = args.scenario_dir / "MANIFEST.csv"
    runner_hash = sha256(pathlib.Path(__file__).resolve())
    binding_hash = sha256(ROOT / "runner" / "commit_binding.py")
    for row in rows:
        row["corpus_manifest_sha256"] = sha256(manifest)
        row["runner_sha256"] = runner_hash
        row["commit_binding_sha256"] = binding_hash
    write_csv(args.detail, rows)
    args.integrity.parent.mkdir(parents=True, exist_ok=True)
    args.integrity.write_text(
        json.dumps(
            {
                "rows": len(rows),
                "profiles": 1 << len(FIELDS),
                "scenarios": len(scenarios),
                "attack_rows": sum(row["scenario_type"] == "attack" for row in rows),
                "control_rows": sum(row["scenario_type"] == "benign" for row in rows),
                "commits": sum(int(row["committed"]) for row in rows),
                "stale_commits": sum(int(row["attack"]) for row in rows),
                "control_tasks": sum(int(row["task"]) for row in rows),
                "ledger_rows": sum(int(row["ledger_rows"]) for row in rows),
                "fields": list(FIELDS),
                "field_to_family": FIELD_TO_FAMILY,
                "corpus_manifest_sha256": sha256(manifest),
                "runner_sha256": runner_hash,
                "commit_binding_sha256": binding_hash,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"receipt-mask ablation completed: rows={len(rows)} "
        f"profiles={1 << len(FIELDS)} scenarios={len(scenarios)}"
    )


if __name__ == "__main__":
    main()
