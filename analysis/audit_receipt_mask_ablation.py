#!/usr/bin/env python3
"""Independently audit the complete receipt-profile ablation matrix."""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
from collections import defaultdict
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
FIELDS = (
    "principal",
    "authorization_version",
    "exact_effect",
    "expiry",
    "confirmation_nonce",
)
FAMILY_FOR_FIELD = {
    "principal": "principal-switch",
    "authorization_version": "authorization-revocation",
    "exact_effect": "effect-substitution",
    "expiry": "lease-expiry",
    "confirmation_nonce": "confirmation-replay",
}
FAMILIES = tuple(FAMILY_FOR_FIELD.values())
EXPECTED_ROWS = 32 * 150


def read_rows(path: pathlib.Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    integer_fields = (
        "profile_mask",
        "committed",
        "attack",
        "task",
        "expected_valid_at_commit",
        "ledger_rows",
    )
    for row in rows:
        for field in integer_fields:
            row[field] = int(row[field])
    return rows


def disabled_fields(mask: int) -> tuple[str, ...]:
    return tuple(
        field for index, field in enumerate(FIELDS) if not (mask & (1 << index))
    )


def validate(rows: list[dict[str, Any]]) -> None:
    if len(rows) != EXPECTED_ROWS:
        raise ValueError(f"expected {EXPECTED_ROWS} rows, found {len(rows)}")
    masks = set(range(1 << len(FIELDS)))
    scenario_ids = {row["scenario_id"] for row in rows}
    observed = {(row["profile_mask"], row["scenario_id"]) for row in rows}
    expected = {(mask, scenario_id) for mask in masks for scenario_id in scenario_ids}
    if observed != expected or len(scenario_ids) != 150:
        raise ValueError("profile/scenario key set is not the 32x150 matrix")
    if {row["family"] for row in rows} != set(FAMILIES):
        raise ValueError("unexpected invalidation family")
    for row in rows:
        if row["ledger_rows"] != row["committed"]:
            raise ValueError(f"ledger mismatch for {row['profile_mask']}/{row['scenario_id']}")
        if row["attack"] != int(row["committed"] and not row["expected_valid_at_commit"]):
            raise ValueError(f"attack label mismatch for {row['profile_mask']}/{row['scenario_id']}")
        if row["task"] != int(row["committed"] and row["expected_valid_at_commit"]):
            raise ValueError(f"task label mismatch for {row['profile_mask']}/{row['scenario_id']}")


def summarize(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_mask_family: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_mask_family[(row["profile_mask"], row["family"])].append(row)
    profile_rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    for mask in range(1 << len(FIELDS)):
        profile_rows.append(
            {
                "profile_mask": mask,
                "profile_hex": f"0x{mask:02x}",
                "disabled_fields": "+".join(disabled_fields(mask)) or "none",
                "attack_n": sum(row["scenario_type"] == "attack" for row in rows if row["profile_mask"] == mask),
                "attack_yes": sum(row["attack"] for row in rows if row["profile_mask"] == mask),
                "control_n": sum(row["scenario_type"] == "benign" for row in rows if row["profile_mask"] == mask),
                "control_tasks": sum(row["task"] for row in rows if row["profile_mask"] == mask),
            }
        )
        for family in FAMILIES:
            selected = by_mask_family[(mask, family)]
            attacks = [row for row in selected if row["scenario_type"] == "attack"]
            controls = [row for row in selected if row["scenario_type"] == "benign"]
            field = next(name for name, value in FAMILY_FOR_FIELD.items() if value == family)
            expected_attack = 20 if field in disabled_fields(mask) else 0
            actual_attack = sum(row["attack"] for row in attacks)
            actual_tasks = sum(row["task"] for row in controls)
            if actual_attack != expected_attack or actual_tasks != 10:
                raise ValueError(
                    f"unexpected composition at mask={mask} family={family}: "
                    f"attack={actual_attack}/{expected_attack} controls={actual_tasks}/10"
                )
            family_rows.append(
                {
                    "profile_mask": mask,
                    "profile_hex": f"0x{mask:02x}",
                    "disabled_fields": "+".join(disabled_fields(mask)) or "none",
                    "family": family,
                    "matching_field": field,
                    "attack_n": len(attacks),
                    "attack_yes": actual_attack,
                    "expected_attack_yes": expected_attack,
                    "control_n": len(controls),
                    "control_tasks": actual_tasks,
                }
            )
    return profile_rows, family_rows


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
        default=ROOT / "analysis" / "receipt_mask_ablation_detail.csv",
    )
    parser.add_argument(
        "--output-prefix",
        type=pathlib.Path,
        default=ROOT / "analysis" / "receipt_mask_ablation",
    )
    args = parser.parse_args()
    rows = read_rows(args.detail)
    validate(rows)
    profile_rows, family_rows = summarize(rows)
    write_csv(pathlib.Path(f"{args.output_prefix}_summary.csv"), profile_rows)
    write_csv(pathlib.Path(f"{args.output_prefix}_family.csv"), family_rows)
    integrity = {
        "rows": len(rows),
        "profiles": len(profile_rows),
        "families": len(FAMILIES),
        "unique_keys": len({(row["profile_mask"], row["scenario_id"]) for row in rows}),
        "attack_rows": sum(row["scenario_type"] == "attack" for row in rows),
        "control_rows": sum(row["scenario_type"] == "benign" for row in rows),
        "commits": sum(row["committed"] for row in rows),
        "stale_commits": sum(row["attack"] for row in rows),
        "control_tasks": sum(row["task"] for row in rows),
        "ledger_rows": sum(row["ledger_rows"] for row in rows),
        "all_composition_checks": True,
        "stable_controls_per_profile": sorted(
            {row["control_tasks"] for row in profile_rows}
        ),
        "full_profile_attack_successes": next(
            row["attack_yes"] for row in profile_rows if row["profile_mask"] == 31
        ),
    }
    pathlib.Path(f"{args.output_prefix}_integrity.json").write_text(
        json.dumps(integrity, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"receipt-mask audit passed: rows={len(rows)} profiles={len(profile_rows)} "
        f"families={len(FAMILIES)}"
    )


if __name__ == "__main__":
    main()
