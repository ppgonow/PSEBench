#!/usr/bin/env python3
"""Verify that declared ACSAC-review responses retain evidence and paper text."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ReviewItem:
    item_id: str
    concern: str
    status: str
    evidence: tuple[str, ...]
    paper_file: str
    paper_fragment: str
    remaining: str


ITEMS = (
    ReviewItem(
        "A-scale",
        "small and underpowered defense conditions",
        "substantially-addressed",
        (
            "scenarios/hybrid-adaptive-heldout/MANIFEST.csv",
            "scenarios/fresh-authorization-heldout/MANIFEST.csv",
            "scenarios/fresh-noncron-authorization-heldout/MANIFEST.csv",
            "scenarios/multitool-chain-heldout/MANIFEST.csv",
            "analysis/network_schedule_detail.csv",
            "analysis/network_schedule_paired.csv",
        ),
        "src/sections/evaluation.tex",
        "We organize the evidence around four questions and three primary layers",
        "Primary live matched slices remain smaller than deterministic replays.",
    ),
    ReviewItem(
        "A-intervals",
        "Wilson intervals missing from headline cells",
        "addressed",
        (
            "analysis/independent_unit_inventory.csv",
            "analysis/independent_paired_primary.csv",
            "analysis/infocom_claim_audit.py",
            "analysis/infocom_claim_audit.csv",
        ),
        "src/sections/evaluation.tex",
        "Wilson intervals apply only to distinct scenarios or templates within one fixed condition",
        "Repeated-configuration inventory counts are descriptive; small paired cells retain wide intervals.",
    ),
    ReviewItem(
        "A-shared-vocabulary",
        "guard and labels share the same lexical rule vocabulary",
        "substantially-addressed",
        (
            "runner/effect_boundary.py",
            "scenarios/hybrid-adaptive-heldout/MANIFEST.csv",
            "scenarios/fresh-authorization-heldout/RULE_SNAPSHOT_SHA256.txt",
            "scenarios/adaptive-native-holdout/MANIFEST_SHA256.txt",
            "analysis/adaptive_native_fork_schema_neutral_postrun_audit_integrity.csv",
        ),
        "src/sections/psebench_iacg.tex",
        "the same conversation is cloned into permissive and IACG continuations",
        "Request inference remains deterministic; the native fork removes shared proposal resampling but uses synthetic scenarios.",
    ),
    ReviewItem(
        "A-adaptive",
        "no attacker targeting the IACG rule table",
        "substantially-addressed",
        (
            "analysis/heldout_adaptive_summary.csv",
            "analysis/fresh_authorization_semantic_denied_summary.csv",
            "analysis/fresh_authorization_semantic_confirmed_summary.csv",
            "scenarios/adaptive-native-holdout/MANIFEST.csv",
            "analysis/adaptive_native_fork_schema_neutral_summary.csv",
            "analysis/adaptive_native_fork_schema_neutral_postrun_audit_paired.csv",
        ),
        "src/sections/evaluation.tex",
        "same-scenario schema-neutral replication changing only that description",
        "The strong Grok effect remains concentrated in file/recipient units; GPT has two recipient discordances and no cross-provider claim is available.",
    ),
    ReviewItem(
        "A-closest-defenses",
        "Task Shield and Prompt Flow Integrity absent or untested",
        "partially-addressed",
        ("runner/baseline_policies.py", "analysis/heldout_adaptive_summary.csv"),
        "src/sections/related_work.tex",
        "All literature-inspired rows are typed adaptations rather than official reproductions",
        "Official Task Shield is LLM-based and no official code link was published; no official run is claimed.",
    ),
    ReviewItem(
        "A-artifact",
        "no anonymous artifact link",
        "partially-addressed",
        ("ANONYMIZATION.md", "ARTIFACT_MANIFEST.md", "scripts/make_anonymous_archive.sh"),
        "src/sections/disclosures.tex",
        "anonymized artifact",
        "The verified ZIP exists locally; an account-neutral hosted URL is still required.",
    ),
    ReviewItem(
        "B-novelty",
        "difference from authorization and stored-injection work unclear",
        "addressed",
        ("results/STAGE_SUMMARY_2026-07-15_INFOCOM_REVIEW_RESPONSE_AUDIT.md",),
        "src/sections/related_work.tex",
        "whether even ephemeral untrusted content enlarges",
        "Claims remain limited to the PSE evaluation lens and reference monitor.",
    ),
    ReviewItem(
        "B-workflows",
        "need multi-tool, non-cron, and complex authorization workflows",
        "substantially-addressed",
        (
            "scenarios/multitool-chain-heldout/MANIFEST.csv",
            "scenarios/fresh-noncron-authorization-heldout/MANIFEST.csv",
            "scenarios/commit-race-heldout/MANIFEST.csv",
            "analysis/multiprocess_commit_race_summary.csv",
            "analysis/multiprocess_commit_race_audit_integrity.csv",
            "runner/run_multiprocess_commit_race.py",
            "analysis/container_commit_race_summary.csv",
            "analysis/container_commit_race_topology.csv",
            "analysis/container_commit_race_audit_integrity.csv",
            "runner/run_container_commit_race.py",
            "analysis/multihost_commit_race_summary.csv",
            "analysis/multihost_commit_race_topology.csv",
            "analysis/multihost_commit_race_audit_integrity.csv",
            "runner/run_multihost_commit_race.py",
            "analysis/network_schedule_detail.csv",
            "analysis/network_schedule_inference.csv",
            "analysis/network_schedule_paired.csv",
            "runner/run_network_schedule_matrix.py",
            "analysis/service_integrated_commit_detail.csv",
            "analysis/service_integrated_commit_integrity.csv",
            "runner/run_service_integrated_commit.py",
            "runner/service_integrated_commit.py",
            "analysis/postgres_integrated_commit_detail.csv",
            "analysis/postgres_integrated_commit_integrity.csv",
            "analysis/postgres_integrated_commit_metadata.csv",
            "analysis/audit_postgres_integrated_commit.py",
            "runner/run_postgres_integrated_commit.py",
            "runner/postgres_integrated_commit.py",
        ),
        "src/sections/discussion_limitations.tex",
        "Three SSH-relayed instances do not establish separate administration",
        "Atomicity is established within single SQLite and PostgreSQL effect services; cross-database commit, live multi-turn interaction, and independently administered services remain future work.",
    ),
    ReviewItem(
        "B-end-to-end",
        "cross-model evidence is decision-only rather than end-to-end",
        "substantially-addressed",
        (
            "analysis/infocom_heldout_live20_quality.csv",
            "results/STAGE_SUMMARY_2026-07-15_INFOCOM_AGENTDOJO_SMOKE.md",
            "analysis/native_e2e48_summary.csv",
            "analysis/native_e2e48_final.jsonl",
            "results/STAGE_SUMMARY_2026-07-16_INFOCOM_NATIVE_E2E48_RESULT.md",
            "analysis/adaptive_native_fork_schema_neutral_final.jsonl",
            "analysis/adaptive_native_fork_schema_neutral_postrun_audit_integrity.csv",
            "results/STAGE_SUMMARY_2026-07-17_INFOCOM_ADAPTIVE_NATIVE_SCHEMA_NEUTRAL_RESULT.md",
        ),
        "src/sections/evaluation.tex",
        "The main end-to-end estimate comes from the adaptive native fork: 80 frozen instances per requested alias",
        "The schema-neutral proposal-bearing replication is complete across four author-verified requested aliases, but synthetic scenarios do not establish broad provider-independent robustness.",
    ),
)


def audit(paper_root: Optional[Path] = None) -> tuple[list[dict], list[str]]:
    paper_root = ROOT if paper_root is None else paper_root
    rows = []
    failures = []
    for item in ITEMS:
        missing = [path for path in item.evidence if not (ROOT / path).exists()]
        paper_path = paper_root / item.paper_file
        if paper_path.exists():
            paper_status = (
                "pass"
                if item.paper_fragment in paper_path.read_text(encoding="utf-8")
                else "fail"
            )
        else:
            paper_status = "not_checked"
        if missing or paper_status == "fail":
            failures.append(item.item_id)
        rows.append(
            {
                "item_id": item.item_id,
                "concern": item.concern,
                "resolution_status": item.status,
                "evidence_status": "pass" if not missing else "missing: " + ";".join(missing),
                "paper_status": paper_status,
                "remaining_boundary": item.remaining,
            }
        )
    return rows, failures


def main() -> None:
    output = ROOT / "analysis" / "reviewer_response_audit.csv"
    rows, failures = audit()
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    checked = sum(row["paper_status"] != "not_checked" for row in rows)
    statuses = {status: sum(row["resolution_status"] == status for row in rows) for status in sorted({row["resolution_status"] for row in rows})}
    print(
        f"review_items={len(rows)} paper_checked={checked} failures={len(failures)} "
        + " ".join(f"{key}={value}" for key, value in statuses.items())
    )
    print(output)
    if failures:
        raise SystemExit("review response audit failed: " + ", ".join(failures))


if __name__ == "__main__":
    main()
