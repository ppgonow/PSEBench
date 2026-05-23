#!/usr/bin/env python3
"""Generate reviewer-gap tables from existing artifacts.

These tables address two evidence-quality questions without creating new run
outcomes: whether the beyond-cron families show the same qualitative pattern,
and how much of the reported labeling is independently checkable by artifact
oracles.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fmt_count(rate: str, n: int) -> str:
    successes = int(round(float(rate) * n))
    return f"{successes}/{n}"


def aggregate_run(run_name: str) -> dict[str, int]:
    run_dir = ROOT / "results" / "runs" / run_name
    out = {"n": 0, "attack": 0, "task": 0, "confirm": 0}
    for final_path in sorted(run_dir.glob("*/final.json")):
        final = json.loads(final_path.read_text(encoding="utf-8"))
        labels = final.get("manual_labels") or {}
        out["n"] += 1
        out["attack"] += int(labels.get("attack_succeeded") == "yes")
        out["task"] += int(labels.get("task_completed") == "yes")
        out["confirm"] += int(bool(labels.get("confirmation_triggered")))
    return out


def fmt_counts(values: dict[str, int], key: str) -> str:
    return f"{values[key]}/{values['n']}"


def noncron_replication() -> None:
    rows: list[dict[str, object]] = []
    specs = [
        (
            "File persistence",
            "riskfix2-noncron-file-permissive",
            "riskfix2-noncron-file-iacg",
            "riskfix2-noncron-file-legit-iacg",
            "riskfix2-noncron-file-legit-firewall",
        ),
        (
            "Calendar recurrence",
            "riskfix2-noncron-calendar-permissive",
            "riskfix2-noncron-calendar-iacg",
            "riskfix2-noncron-calendar-legit-iacg",
            "riskfix2-noncron-calendar-legit-firewall",
        ),
        (
            "Recipient hijack",
            "riskfix2-noncron-recipient-permissive",
            "riskfix2-noncron-recipient-iacg",
            "",
            "",
        ),
    ]
    for family, perm_run, iacg_run, legit_iacg_run, legit_firewall_run in specs:
        perm = aggregate_run(perm_run)
        iacg = aggregate_run(iacg_run)
        legit_iacg = aggregate_run(legit_iacg_run) if legit_iacg_run else {"n": 0, "task": 0}
        legit_firewall = aggregate_run(legit_firewall_run) if legit_firewall_run else {"n": 0, "task": 0}
        rows.append(
            {
                "family": family,
                "permissive_run": perm_run,
                "permissive_ASR": fmt_counts(perm, "attack"),
                "permissive_TCR": fmt_counts(perm, "task"),
                "IACG_run": iacg_run,
                "IACG_ASR": fmt_counts(iacg, "attack"),
                "IACG_TCR": fmt_counts(iacg, "task"),
                "IACG_legitimate_persistent_TCR": fmt_counts(legit_iacg, "task") if legit_iacg["n"] else "n/a",
                "firewall_legitimate_persistent_TCR": fmt_counts(legit_firewall, "task") if legit_firewall["n"] else "n/a",
            }
        )
    write_csv(ANALYSIS / "noncron_replication_summary.csv", rows)


def evidence_tier_summary() -> None:
    cron = read_csv(ANALYSIS / "auto_oracle_agreement_summary.csv")[0]
    noncron = next(
        row
        for row in read_csv(ANALYSIS / "auto_oracle_noncron_summary.csv")
        if row["family"] == "ALL"
    )
    artifact_oracle_total = int(cron["n"]) + int(noncron["n"])
    rows = [
        {
            "tier": "primary benchmark contrast",
            "evidence": "original labeled tool-induction vs hybrid legitimate-tool slice",
            "n": 141,
            "role_in_paper": "main evidence for evaluation blind spot",
            "claim_boundary": "shows concentration of observed failures in hybrid legitimate-tool workflows",
        },
        {
            "tier": "matched reference-monitor slice",
            "evidence": "core cron permissive vs IACG 2x2 plus adaptive/live replicas",
            "n": "10 per matched condition",
            "role_in_paper": "main enforcement mechanism check",
            "claim_boundary": "tests the isolated one-shot-to-recurring boundary, not all agent behavior",
        },
        {
            "tier": "non-cron mechanism replication",
            "evidence": "riskfix2 file, calendar, and recipient artifact-backed runs",
            "n": 64,
            "role_in_paper": "supporting evidence against cron-only explanation",
            "claim_boundary": "replicates the authorization-boundary pattern but remains smaller than the cron slice",
        },
        {
            "tier": "artifact-oracle cross-check",
            "evidence": "cron and non-cron machine-checkable finalized artifacts",
            "n": artifact_oracle_total,
            "role_in_paper": "label reliability check",
            "claim_boundary": "independent artifact oracle, not full human inter-annotator agreement",
        },
        {
            "tier": "model-driven/live supporting slice",
            "evidence": "small model-driven and live replica runs from existing artifacts",
            "n": "small supporting slices",
            "role_in_paper": "qualitative robustness check",
            "claim_boundary": "not a comprehensive cross-model benchmark",
        },
    ]
    write_csv(ANALYSIS / "evidence_tier_summary.csv", rows)


def oracle_coverage() -> None:
    cron = read_csv(ANALYSIS / "auto_oracle_agreement_summary.csv")[0]
    noncron = next(
        row
        for row in read_csv(ANALYSIS / "auto_oracle_noncron_summary.csv")
        if row["family"] == "ALL"
    )
    cron_n = int(cron["n"])
    noncron_n = int(noncron["n"])
    rows = [
        {
            "slice": "Cron escalation artifact oracle",
            "n": cron_n,
            "joint_agreement": f"{cron['both_agree']}/{cron_n}",
            "agreement_rate": cron["joint_agreement_rate"],
            "scope": "one-shot or ambiguous cron escalation artifacts",
        },
        {
            "slice": "Non-cron artifact oracle",
            "n": noncron_n,
            "joint_agreement": f"{noncron['joint_agree']}/{noncron_n}",
            "agreement_rate": noncron["joint_agreement_rate"],
            "scope": "file, calendar, recipient, and H-web artifact-backed families",
        },
        {
            "slice": "Artifact-oracle covered total",
            "n": cron_n + noncron_n,
            "joint_agreement": f"{int(cron['both_agree']) + int(noncron['joint_agree'])}/{cron_n + noncron_n}",
            "agreement_rate": round((int(cron["both_agree"]) + int(noncron["joint_agree"])) / (cron_n + noncron_n), 3),
            "scope": "machine-checkable reported run artifacts",
        },
    ]
    write_csv(ANALYSIS / "artifact_oracle_coverage_summary.csv", rows)


def main() -> None:
    noncron_replication()
    evidence_tier_summary()
    oracle_coverage()
    print(ANALYSIS / "noncron_replication_summary.csv")
    print(ANALYSIS / "evidence_tier_summary.csv")
    print(ANALYSIS / "artifact_oracle_coverage_summary.csv")


if __name__ == "__main__":
    main()
