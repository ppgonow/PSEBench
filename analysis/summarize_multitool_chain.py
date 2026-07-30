#!/usr/bin/env python3
"""Summarize multi-tool chain replay with Wilson and paired statistics."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
import math
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def exact_mcnemar(b: int, c: int) -> float:
    discordant = b + c
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, i) for i in range(min(b, c) + 1))
    return min(1.0, 2 * tail / (2**discordant))


def load_rows(root: pathlib.Path) -> list[dict]:
    rows = []
    for path in sorted(root.rglob("final.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        labels = payload.get("manual_labels") or {}
        rows.append(
            {
                "scenario_id": payload["scenario_id"],
                "family": payload.get("family", "unknown"),
                "policy": (payload.get("guard") or {}).get("guard_policy", "unknown"),
                "attack": labels.get("attack_succeeded") == "yes",
                "task": labels.get("task_completed") == "yes",
                "path": str(path.relative_to(ROOT)),
            }
        )
    return rows


def write_csv(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[("overall", "all", row["policy"])].append(row)
        groups[("family", row["family"], row["policy"])].append(row)
    output = []
    for (scope, family, policy), items in sorted(groups.items()):
        n = len(items)
        attack_yes = sum(item["attack"] for item in items)
        task_yes = sum(item["task"] for item in items)
        attack_ci = wilson(attack_yes, n)
        task_ci = wilson(task_yes, n)
        output.append(
            {
                "scope": scope,
                "family": family,
                "policy": policy,
                "n": n,
                "attack_yes": attack_yes,
                "ASR": round(attack_yes / n, 6),
                "ASR_CI_low": round(attack_ci[0], 6),
                "ASR_CI_high": round(attack_ci[1], 6),
                "task_yes": task_yes,
                "TCR": round(task_yes / n, 6),
                "TCR_CI_low": round(task_ci[0], 6),
                "TCR_CI_high": round(task_ci[1], 6),
            }
        )
    return output


def paired(rows: list[dict]) -> list[dict]:
    by_key = {(row["policy"], row["scenario_id"]): row for row in rows}
    families = ["all", *sorted({row["family"] for row in rows})]
    output = []
    for family in families:
        ids = sorted(
            {
                row["scenario_id"]
                for row in rows
                if family == "all" or row["family"] == family
            }
        )
        b = sum(
            by_key[("permissive", scenario_id)]["attack"]
            and not by_key[("IACG", scenario_id)]["attack"]
            for scenario_id in ids
        )
        c = sum(
            not by_key[("permissive", scenario_id)]["attack"]
            and by_key[("IACG", scenario_id)]["attack"]
            for scenario_id in ids
        )
        output.append(
            {
                "family": family,
                "n_pairs": len(ids),
                "permissive_yes_iacg_no": b,
                "permissive_no_iacg_yes": c,
                "exact_mcnemar_p": exact_mcnemar(b, c),
            }
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=ROOT / "results" / "multitool_chain_runs",
    )
    parser.add_argument(
        "--output-prefix",
        type=pathlib.Path,
        default=ROOT / "analysis" / "multitool_chain",
    )
    args = parser.parse_args()
    rows = load_rows(args.root)
    if not rows:
        raise SystemExit(f"no finalized chain replays found under {args.root}")
    details = [
        {
            **row,
            "attack": int(row["attack"]),
            "task": int(row["task"]),
        }
        for row in rows
    ]
    write_csv(pathlib.Path(f"{args.output_prefix}_detail.csv"), details)
    write_csv(pathlib.Path(f"{args.output_prefix}_summary.csv"), summarize(rows))
    write_csv(pathlib.Path(f"{args.output_prefix}_paired.csv"), paired(rows))
    print(f"summarized {len(rows)} policy/scenario rows")


if __name__ == "__main__":
    main()
