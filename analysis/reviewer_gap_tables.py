#!/usr/bin/env python3
"""Generate reviewer-facing summary tables for prompt-only and oracle coverage.

The tables are intentionally derived from existing finalized runs and summary
files. They do not create new experimental outcomes.
"""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def count(row: dict[str, str], key: str) -> int:
    value = row.get(key, "")
    return int(float(value)) if value not in ("", None) else 0


def fmt_rate(successes: int, n: int) -> str:
    return f"{successes}/{n}" if n else "0/0"


def prompt_only_table() -> None:
    by_run = {row["key"]: row for row in read_csv(ANALYSIS / "main_table_by_run.csv")}
    rows = []
    specs = [
        (
            "model prompt-only, hardened",
            "md2-model-strict",
            "Strict instruction-level decision prompt; no action-boundary guard.",
        ),
        (
            "model prompt-only, permissive",
            "md2-model-permissive",
            "Permissive instruction-level decision prompt; no action-boundary guard.",
        ),
        (
            "decision proxy, strict prompt policy",
            "p2-p2-proxy-strict",
            "Deterministic proxy for a strict prompt-only decision policy.",
        ),
        (
            "decision proxy, naive prompt policy",
            "dp1-decision-proxy-naive",
            "Deterministic proxy for a naive prompt-following decision policy.",
        ),
        (
            "IACG action-boundary guard",
            "g2-permissive-guard",
            "Tool-layer authorization check applied before action execution.",
        ),
    ]
    for label, key, note in specs:
        row = by_run[key]
        n = count(row, "n")
        attack = count(row, "attack_yes")
        task = count(row, "task_yes")
        rows.append(
            {
                "condition": label,
                "run_key": key,
                "n": n,
                "ASR": fmt_rate(attack, n),
                "TCR": fmt_rate(task, n),
                "ASR_CI": f"[{row.get('asr_ci_low', '')}, {row.get('asr_ci_high', '')}]",
                "TCR_CI": f"[{row.get('tcr_ci_low', '')}, {row.get('tcr_ci_high', '')}]",
                "interpretation": note,
            }
        )
    write_csv(ANALYSIS / "prompt_only_baseline_summary.csv", rows)


def oracle_coverage_table() -> None:
    family = {row["key"]: row for row in read_csv(ANALYSIS / "main_table_by_family_plus_persistent.csv")}
    auto = read_csv(ANALYSIS / "auto_oracle_agreement_summary.csv")
    joint = auto[0]
    auto_n = int(joint["n"])
    auto_agree = int(joint["both_agree"])
    noncron_auto = read_csv(ANALYSIS / "auto_oracle_noncron_summary.csv")
    noncron_all = next(row for row in noncron_auto if row["family"] == "ALL")
    noncron_n = int(noncron_all["n"])
    noncron_agree = int(noncron_all["joint_agree"])

    attack_only_n = sum(count(family[key], "n") for key in ["A-web-exec", "A-web-msg", "A-msg-cron", "A-web-nodes"])

    rows = [
        {
            "slice": "CLI-backed one-shot/ambiguous cron escalation",
            "n": auto_n,
            "label_support": "automatic final-artifact oracle plus stored manual labels",
            "agreement": f"{auto_agree}/{auto_n}",
            "remaining_gap": "Oracle is scoped to cron escalation only.",
        },
        {
            "slice": "Non-cron artifact-backed hybrid families",
            "n": noncron_n,
            "label_support": "artifact-level oracle plus stored manual labels",
            "agreement": f"{noncron_agree}/{noncron_n}",
            "remaining_gap": "Covers file, calendar, recipient, and H-web negative families.",
        },
        {
            "slice": "Tool-induction families",
            "n": attack_only_n,
            "label_support": "structured artifacts plus manual labels",
            "agreement": "not independently double-labeled",
            "remaining_gap": "Reported mainly as contrast against hybrid workflows.",
        },
    ]
    write_csv(ANALYSIS / "oracle_coverage_summary.csv", rows)


def main() -> None:
    prompt_only_table()
    oracle_coverage_table()


if __name__ == "__main__":
    main()
