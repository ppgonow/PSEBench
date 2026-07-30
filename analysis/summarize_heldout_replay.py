#!/usr/bin/env python3
"""Summarize action-boundary replay with Wilson intervals and pairing."""

from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
from collections import defaultdict

import yaml


def wilson(k: int, n: int) -> tuple[float, float]:
    if not n:
        return 0.0, 0.0
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / d
    return max(0.0, c - m), min(1.0, c + m)


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def _fallback_suite(scenario: dict) -> str:
    intent = (scenario.get("intent") or {}).get("user_intent", "unknown")
    if scenario.get("type") == "benign" and intent == "recurring":
        return "legitimate-persistence"
    return "heldout-attack"


def load(root: pathlib.Path) -> list[dict]:
    rows = []
    for path in sorted(root.glob("*/*/final.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        scenario_path = path.parent / "scenario.yaml"
        scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
        labels = data.get("manual_labels", {})
        runtime = data.get("guard", {}).get("runtime_authorization", {})
        replay = data.get("replay", {})
        authorization_mode = replay.get("authorization_mode", "lexical")
        confirmation_mode = replay.get("confirmation_mode", "deny")
        rows.append(
            {
                "policy": path.parent.parent.name,
                "authorization_mode": authorization_mode,
                "confirmation_mode": confirmation_mode,
                "condition": f"{authorization_mode}+{confirmation_mode}",
                "scenario_id": data["scenario_id"],
                "suite": scenario.get("suite", _fallback_suite(scenario)),
                "family": scenario.get("family", "cron"),
                "scenario_type": scenario.get("type", "unknown"),
                "style": data.get("attack_style", "unknown"),
                "runtime_intent": runtime.get("intent", "legacy"),
                "guard_decision": data.get("guard", {}).get("guard_decision", "unknown"),
                "attack": labels.get("attack_succeeded") == "yes",
                "task": labels.get("task_completed") == "yes",
                "false_block": bool(labels.get("false_block", False)),
                "confirmation": bool(labels.get("confirmation_triggered", False)),
            }
        )
    return rows


def _metric(values: list[dict], key: str, *, eligible=None) -> tuple[int, int, float | None, float | None, float | None]:
    selected = [row for row in values if eligible is None or eligible(row)]
    n = len(selected)
    yes = sum(bool(row[key]) for row in selected)
    if n == 0:
        return n, yes, None, None, None
    low, high = wilson(yes, n)
    return n, yes, yes / n, low, high


def _summary_row(policy: str, condition: str, scope: str, values: list[dict]) -> dict:
    attack_n, attack_yes, asr, asr_low, asr_high = _metric(
        values, "attack", eligible=lambda row: row["scenario_type"] == "attack"
    )
    task_n, task_yes, tcr, tcr_low, tcr_high = _metric(values, "task")
    benign_n, false_block_yes, false_block_rate, false_block_low, false_block_high = _metric(
        values, "false_block", eligible=lambda row: row["scenario_type"] == "benign"
    )
    _, confirmation_yes, confirmation_rate, confirmation_low, confirmation_high = _metric(values, "confirmation")
    return {
        "scope": scope,
        "policy": policy,
        "condition": condition,
        "n": len(values),
        "attack_n": attack_n,
        "attack_yes": attack_yes,
        "ASR": asr,
        "ASR_CI_low": asr_low,
        "ASR_CI_high": asr_high,
        "task_n": task_n,
        "task_yes": task_yes,
        "TCR": tcr,
        "TCR_CI_low": tcr_low,
        "TCR_CI_high": tcr_high,
        "benign_n": benign_n,
        "false_block_yes": false_block_yes,
        "false_block_rate": false_block_rate,
        "false_block_CI_low": false_block_low,
        "false_block_CI_high": false_block_high,
        "confirmation_yes": confirmation_yes,
        "confirmation_rate": confirmation_rate,
        "confirmation_CI_low": confirmation_low,
        "confirmation_CI_high": confirmation_high,
    }


def _paired_rows(rows: list[dict]) -> list[dict]:
    output = []
    scopes = ["overall", *sorted({row["suite"] for row in rows})]
    conditions = sorted({row["condition"] for row in rows})
    policies = sorted({row["policy"] for row in rows} - {"permissive"})
    outcomes = {
        "attack": lambda row: row["scenario_type"] == "attack",
        "task": lambda row: True,
        "false_block": lambda row: row["scenario_type"] == "benign",
        "confirmation": lambda row: True,
    }
    for condition in conditions:
        condition_rows = [row for row in rows if row["condition"] == condition]
        for scope in scopes:
            scoped = condition_rows if scope == "overall" else [row for row in condition_rows if row["suite"] == scope]
            baseline = {row["scenario_id"]: row for row in scoped if row["policy"] == "permissive"}
            for policy in policies:
                candidate = {row["scenario_id"]: row for row in scoped if row["policy"] == policy}
                for outcome, eligible in outcomes.items():
                    common = [key for key in sorted(set(baseline) & set(candidate)) if eligible(baseline[key])]
                    b = sum(baseline[key][outcome] and not candidate[key][outcome] for key in common)
                    c = sum(not baseline[key][outcome] and candidate[key][outcome] for key in common)
                    output.append(
                        {
                            "condition": condition,
                            "scope": scope,
                            "baseline": "permissive",
                            "policy": policy,
                            "outcome": outcome,
                            "n_paired": len(common),
                            "baseline_yes_policy_no": b,
                            "baseline_no_policy_yes": c,
                            "mcnemar_exact_p": mcnemar_exact(b, c),
                        }
                    )
    return output


def _write_csv(path: pathlib.Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path("results/heldout_runs"))
    parser.add_argument("--output-prefix", type=pathlib.Path, default=pathlib.Path("analysis/heldout_adaptive"))
    args = parser.parse_args()
    rows = load(args.root)
    if not rows:
        raise SystemExit(f"no replay outputs under {args.root}")

    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["policy"], row["condition"], "overall")].append(row)
        grouped[(row["policy"], row["condition"], row["suite"])].append(row)
    summary = [
        _summary_row(policy, condition, scope, values)
        for (policy, condition, scope), values in sorted(grouped.items())
    ]

    by_style = []
    style_groups = defaultdict(list)
    for row in rows:
        if row["scenario_type"] == "attack":
            style_groups[(row["policy"], row["condition"], row["suite"], row["style"])].append(row)
    for (policy, condition, suite, style), values in sorted(style_groups.items()):
        n, attacks, asr, low, high = _metric(values, "attack")
        by_style.append(
            {
                "policy": policy,
                "condition": condition,
                "suite": suite,
                "style": style,
                "n": n,
                "attack_yes": attacks,
                "ASR": asr,
                "ASR_CI_low": low,
                "ASR_CI_high": high,
            }
        )

    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output_prefix.with_name(args.output_prefix.name + "_summary.csv"), summary)
    _write_csv(args.output_prefix.with_name(args.output_prefix.name + "_paired.csv"), _paired_rows(rows))
    _write_csv(args.output_prefix.with_name(args.output_prefix.name + "_by_style.csv"), by_style)
    _write_csv(args.output_prefix.with_name(args.output_prefix.name + "_detail.csv"), rows)
    print(f"summarized {len(rows)} replay outputs")


if __name__ == "__main__":
    main()
