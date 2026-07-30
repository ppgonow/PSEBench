#!/usr/bin/env python3
"""Independently reconstruct the receipt-field ablation result."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import math
import pathlib
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICIES = (
    "receipt-full",
    "receipt-no-principal",
    "receipt-no-authorization-version",
    "receipt-no-exact-effect",
    "receipt-no-expiry",
    "receipt-no-confirmation-nonce",
    "online-reauthorize-at-commit",
)
FAMILIES = (
    "authorization-revocation",
    "confirmation-replay",
    "effect-substitution",
    "lease-expiry",
    "principal-switch",
)
INTEGER_FIELDS = (
    "committed",
    "attack",
    "task",
    "ledger_rows",
    "expected_valid_at_commit",
)


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if not total:
        return 0.0, 0.0
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(
        (p * (1 - p) + z * z / (4 * total)) / total
    ) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def exact_mcnemar(left_only: int, right_only: int) -> float:
    discordant = left_only + right_only
    if not discordant:
        return 1.0
    tail = sum(
        math.comb(discordant, index)
        for index in range(min(left_only, right_only) + 1)
    )
    return min(1.0, 2 * tail / (2**discordant))


def read_rows(path: pathlib.Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows: list[dict[str, Any]] = list(csv.DictReader(handle))
    for row in rows:
        for field in INTEGER_FIELDS:
            row[field] = int(row[field])
    return rows


def validate(rows: list[dict[str, Any]]) -> None:
    keys = {(row["policy"], row["scenario_id"]) for row in rows}
    ids = {row["scenario_id"] for row in rows}
    expected = {(policy, scenario_id) for policy in POLICIES for scenario_id in ids}
    if len(rows) != 1050 or len(ids) != 150 or keys != expected:
        raise ValueError("detail is not the frozen 1,050-row matrix")
    if {row["family"] for row in rows} != set(FAMILIES):
        raise ValueError("family set differs from the freeze")
    for policy in POLICIES:
        selected = [row for row in rows if row["policy"] == policy]
        if sum(row["scenario_type"] == "attack" for row in selected) != 100:
            raise ValueError(f"attack denominator changed for {policy}")
        if sum(row["scenario_type"] == "benign" for row in selected) != 50:
            raise ValueError(f"control denominator changed for {policy}")
    for row in rows:
        valid = bool(row["expected_valid_at_commit"])
        committed = bool(row["committed"])
        if row["ledger_rows"] != int(committed):
            raise ValueError(f"ledger mismatch: {row}")
        if row["attack"] != int(committed and not valid):
            raise ValueError(f"attack mismatch: {row}")
        if row["task"] != int(committed and valid):
            raise ValueError(f"task mismatch: {row}")


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[("overall", "all", row["policy"])].append(row)
        groups[("family", row["family"], row["policy"])].append(row)
    output: list[dict[str, Any]] = []
    for (scope, family, policy), selected in sorted(groups.items()):
        attacks = [row for row in selected if row["scenario_type"] == "attack"]
        controls = [row for row in selected if row["scenario_type"] == "benign"]
        attack_yes = sum(row["attack"] for row in attacks)
        task_yes = sum(row["task"] for row in controls)
        asr_ci = wilson(attack_yes, len(attacks))
        tcr_ci = wilson(task_yes, len(controls))
        output.append(
            {
                "scope": scope,
                "family": family,
                "policy": policy,
                "attack_n": len(attacks),
                "attack_yes": attack_yes,
                "ASR": round(attack_yes / len(attacks), 6),
                "ASR_CI_low": round(asr_ci[0], 6),
                "ASR_CI_high": round(asr_ci[1], 6),
                "control_n": len(controls),
                "task_yes": task_yes,
                "TCR": round(task_yes / len(controls), 6),
                "TCR_CI_low": round(tcr_ci[0], 6),
                "TCR_CI_high": round(tcr_ci[1], 6),
            }
        )
    return output


def paired(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {(row["policy"], row["scenario_id"]): row for row in rows}
    output: list[dict[str, Any]] = []
    for family in ("all", *FAMILIES):
        ids = sorted(
            {
                row["scenario_id"]
                for row in rows
                if row["scenario_type"] == "attack"
                and (family == "all" or row["family"] == family)
            }
        )
        for policy in POLICIES[1:]:
            full_only = sum(
                indexed[("receipt-full", scenario_id)]["attack"]
                and not indexed[(policy, scenario_id)]["attack"]
                for scenario_id in ids
            )
            comparator_only = sum(
                not indexed[("receipt-full", scenario_id)]["attack"]
                and indexed[(policy, scenario_id)]["attack"]
                for scenario_id in ids
            )
            output.append(
                {
                    "family": family,
                    "comparator": policy,
                    "n_pairs": len(ids),
                    "full_only": full_only,
                    "comparator_only": comparator_only,
                    "exact_mcnemar_p": exact_mcnemar(
                        full_only, comparator_only
                    ),
                }
            )
    return output


def integrity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "rows": len(rows),
            "unique_keys": len({(row["policy"], row["scenario_id"]) for row in rows}),
            "unique_scenarios": len({row["scenario_id"] for row in rows}),
            "attack_rows": sum(row["scenario_type"] == "attack" for row in rows),
            "control_rows": sum(row["scenario_type"] == "benign" for row in rows),
            "commits": sum(row["committed"] for row in rows),
            "stale_commits": sum(row["attack"] for row in rows),
            "control_tasks": sum(row["task"] for row in rows),
            "ledger_rows": sum(row["ledger_rows"] for row in rows),
        }
    ]


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
        default=ROOT / "analysis" / "receipt_field_ablation_detail.csv",
    )
    parser.add_argument(
        "--output-prefix",
        type=pathlib.Path,
        default=ROOT / "analysis" / "receipt_field_ablation",
    )
    args = parser.parse_args()
    rows = read_rows(args.detail)
    validate(rows)
    write_csv(pathlib.Path(f"{args.output_prefix}_summary.csv"), summarize(rows))
    write_csv(pathlib.Path(f"{args.output_prefix}_paired.csv"), paired(rows))
    write_csv(pathlib.Path(f"{args.output_prefix}_integrity.csv"), integrity(rows))
    print("receipt-field audit passed: rows=1050 unique_keys=1050")


if __name__ == "__main__":
    main()
