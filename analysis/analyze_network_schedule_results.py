#!/usr/bin/env python3
"""Derive inferential and benign-latency views from network-schedule detail."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import statistics
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
from audit_network_schedule import (  # noqa: E402
    POLICIES,
    PROFILE_ATTEMPTS,
    percentile,
    read_csv,
    validate,
)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    proportion = k / n
    denominator = 1 + z * z / n
    center = (proportion + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(
        (proportion * (1 - proportion) + z * z / (4 * n)) / n
    ) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def exact_mcnemar(discordant_a: int, discordant_b: int) -> float:
    discordant = discordant_a + discordant_b
    if discordant == 0:
        return 1.0
    smaller = min(discordant_a, discordant_b)
    lower_tail = sum(math.comb(discordant, index) for index in range(smaller + 1))
    return min(1.0, 2.0 * lower_tail / (2**discordant))


def policy_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for profile in PROFILE_ATTEMPTS:
        for policy in POLICIES:
            selected = [
                row
                for row in rows
                if row["profile"] == profile and row["policy"] == policy
            ]
            attacks = [row for row in selected if row["scenario_type"] == "attack"]
            controls = [row for row in selected if row["scenario_type"] == "benign"]
            attack_yes = sum(int(row["attack"]) for row in attacks)
            task_yes = sum(int(row["task"]) for row in controls)
            asr_low, asr_high = wilson(attack_yes, len(attacks))
            tcr_low, tcr_high = wilson(task_yes, len(controls))
            benign_us = [float(row["profile_e2e_us"]) for row in controls]
            output.append(
                {
                    "profile": profile,
                    "policy": policy,
                    "attack_n": len(attacks),
                    "attack_yes": attack_yes,
                    "asr_wilson_low": round(asr_low, 6),
                    "asr_wilson_high": round(asr_high, 6),
                    "control_n": len(controls),
                    "task_yes": task_yes,
                    "tcr_wilson_low": round(tcr_low, 6),
                    "tcr_wilson_high": round(tcr_high, 6),
                    "benign_client_median_ms": round(
                        statistics.median(benign_us) / 1000.0, 3
                    ),
                    "benign_client_p95_ms": round(
                        percentile(benign_us, 0.95) / 1000.0, 3
                    ),
                    "benign_client_p99_ms": round(
                        percentile(benign_us, 0.99) / 1000.0, 3
                    ),
                }
            )
    return output


def family_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    families = sorted({row["family"] for row in rows})
    for profile in PROFILE_ATTEMPTS:
        for policy in POLICIES:
            for family in families:
                selected = [
                    row
                    for row in rows
                    if row["profile"] == profile
                    and row["policy"] == policy
                    and row["family"] == family
                ]
                attacks = [row for row in selected if row["scenario_type"] == "attack"]
                controls = [row for row in selected if row["scenario_type"] == "benign"]
                output.append(
                    {
                        "profile": profile,
                        "policy": policy,
                        "family": family,
                        "attack_n": len(attacks),
                        "attack_yes": sum(int(row["attack"]) for row in attacks),
                        "control_n": len(controls),
                        "task_yes": sum(int(row["task"]) for row in controls),
                    }
                )
    return output


def paired_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for profile in PROFILE_ATTEMPTS:
        by_key = {
            (row["policy"], row["scenario_id"]): int(row["attack"])
            for row in rows
            if row["profile"] == profile and row["scenario_type"] == "attack"
        }
        scenario_ids = sorted(
            scenario_id
            for policy, scenario_id in by_key
            if policy == "check-once"
        )
        check_only = sum(
            by_key[("check-once", scenario_id)] == 1
            and by_key[("receipt-bound", scenario_id)] == 0
            for scenario_id in scenario_ids
        )
        bound_only = sum(
            by_key[("check-once", scenario_id)] == 0
            and by_key[("receipt-bound", scenario_id)] == 1
            for scenario_id in scenario_ids
        )
        output.append(
            {
                "profile": profile,
                "paired_attack_n": len(scenario_ids),
                "check_once_only_attack": check_only,
                "receipt_bound_only_attack": bound_only,
                "exact_mcnemar_p": exact_mcnemar(check_only, bound_only),
            }
        )
    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--detail",
        type=Path,
        default=ROOT / "analysis" / "network_schedule_detail.csv",
    )
    parser.add_argument(
        "--scenario-dir",
        type=Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument(
        "--output-prefix",
        type=Path,
        default=ROOT / "analysis" / "network_schedule",
    )
    args = parser.parse_args()
    rows = read_csv(args.detail)
    validate(rows, args.scenario_dir)
    write_csv(Path(f"{args.output_prefix}_inference.csv"), policy_summary(rows))
    write_csv(Path(f"{args.output_prefix}_by_family.csv"), family_summary(rows))
    write_csv(Path(f"{args.output_prefix}_paired.csv"), paired_summary(rows))
    print(f"network schedule analysis passed: rows={len(rows)}")


if __name__ == "__main__":
    main()
