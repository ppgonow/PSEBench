#!/usr/bin/env python3
"""Summarize paired commit-binding state-machine replay."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
import math
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICIES = ("check-once", "commit-bound")


def wilson(k: int, n: int) -> tuple[float, float]:
    if not n:
        return 0.0, 0.0
    z = 1.96
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def exact_mcnemar(b: int, c: int) -> float:
    discordant = b + c
    if not discordant:
        return 1.0
    tail = sum(math.comb(discordant, i) for i in range(min(b, c) + 1))
    return min(1.0, 2 * tail / (2**discordant))


def load_rows(root: pathlib.Path) -> list[dict]:
    rows = []
    for path in sorted(root.rglob("final.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        labels = payload["manual_labels"]
        guard = payload["guard"]
        rows.append(
            {
                "scenario_id": payload["scenario_id"],
                "family": payload["family"],
                "scenario_type": payload["scenario_type"],
                "policy": guard["guard_policy"],
                "invalidation": guard["pre_registered_invalidation"],
                "attack": labels["attack_succeeded"] == "yes",
                "task": labels["task_completed"] == "yes",
                "path": str(path.relative_to(ROOT)),
            }
        )
    return rows


def summarize(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[("overall", "all", row["policy"])].append(row)
        groups[("family", row["family"], row["policy"])].append(row)
    output = []
    for (scope, family, policy), items in sorted(groups.items()):
        attacks = [item for item in items if item["scenario_type"] == "attack"]
        benign = [item for item in items if item["scenario_type"] == "benign"]
        attack_yes = sum(item["attack"] for item in attacks)
        task_yes = sum(item["task"] for item in benign)
        attack_ci = wilson(attack_yes, len(attacks))
        task_ci = wilson(task_yes, len(benign))
        output.append(
            {
                "scope": scope,
                "family": family,
                "policy": policy,
                "attack_n": len(attacks),
                "attack_yes": attack_yes,
                "ASR": round(attack_yes / len(attacks), 6),
                "ASR_CI_low": round(attack_ci[0], 6),
                "ASR_CI_high": round(attack_ci[1], 6),
                "benign_n": len(benign),
                "task_yes": task_yes,
                "TCR": round(task_yes / len(benign), 6),
                "TCR_CI_low": round(task_ci[0], 6),
                "TCR_CI_high": round(task_ci[1], 6),
            }
        )
    return output


def paired(rows: list[dict]) -> list[dict]:
    by_key = {(row["policy"], row["scenario_id"]): row for row in rows}
    attack_rows = [row for row in rows if row["scenario_type"] == "attack"]
    families = ["all", *sorted({row["family"] for row in attack_rows})]
    output = []
    for family in families:
        ids = sorted(
            {
                row["scenario_id"]
                for row in attack_rows
                if family == "all" or row["family"] == family
            }
        )
        for scenario_id in ids:
            if any((policy, scenario_id) not in by_key for policy in POLICIES):
                raise ValueError(f"missing paired policy result for {scenario_id}")
        b = sum(
            by_key[("check-once", scenario_id)]["attack"]
            and not by_key[("commit-bound", scenario_id)]["attack"]
            for scenario_id in ids
        )
        c = sum(
            not by_key[("check-once", scenario_id)]["attack"]
            and by_key[("commit-bound", scenario_id)]["attack"]
            for scenario_id in ids
        )
        output.append(
            {
                "family": family,
                "n_pairs": len(ids),
                "check_once_yes_commit_bound_no": b,
                "check_once_no_commit_bound_yes": c,
                "exact_mcnemar_p": exact_mcnemar(b, c),
            }
        )
    return output


def write_csv(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", type=pathlib.Path, default=ROOT / "results" / "commit_race_runs"
    )
    parser.add_argument(
        "--output-prefix", type=pathlib.Path, default=ROOT / "analysis" / "commit_race"
    )
    args = parser.parse_args()
    rows = load_rows(args.root)
    if not rows:
        raise SystemExit(f"no finalized commit-race rows under {args.root}")
    expected_policies = set(POLICIES)
    if {row["policy"] for row in rows} != expected_policies:
        raise SystemExit("commit-race summary requires both paired policies")
    details = [{**row, "attack": int(row["attack"]), "task": int(row["task"])} for row in rows]
    write_csv(pathlib.Path(f"{args.output_prefix}_detail.csv"), details)
    write_csv(pathlib.Path(f"{args.output_prefix}_summary.csv"), summarize(rows))
    write_csv(pathlib.Path(f"{args.output_prefix}_paired.csv"), paired(rows))
    print(f"summarized {len(rows)} commit-race policy/scenario rows")


if __name__ == "__main__":
    main()
