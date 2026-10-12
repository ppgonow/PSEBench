#!/usr/bin/env python3
"""Post-hoc task-label correction without rewriting frozen native results."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from same_tool_task_oracle import ORACLE_VERSION, evaluate_task_completion  # noqa: E402


MODELS = ("gpt-5.5", "grok-4.5", "gpt-5.4", "gpt-5.6-sol")
POLICIES = ("permissive", "IACG")
INPUT_NAMES = {
    "gpt-5.5": "same_tool_native_commit_gpt_5_5_final.jsonl",
    "grok-4.5": "same_tool_native_commit_grok_4_5_final.jsonl",
    "gpt-5.4": "same_tool_native_commit_gpt_5_4_final.jsonl",
    "gpt-5.6-sol": "same_tool_native_commit_gpt_5_6_sol_final.jsonl",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        entries = list(csv.DictReader(handle))
    if len(entries) != 96 or len({item["scenario_id"] for item in entries}) != 96:
        raise ValueError("manifest must contain 96 unique scenarios")
    scenarios, metadata = {}, {}
    for item in entries:
        source = ROOT / item["source_path"]
        if sha256(source) != item["sha256"]:
            raise ValueError(f"scenario hash mismatch: {item['scenario_id']}")
        scenario = yaml.safe_load(source.read_text(encoding="utf-8"))
        if scenario["id"] != item["scenario_id"]:
            raise ValueError("scenario identity mismatch")
        for field in ("template_id", "workflow", "carrier", "exposure"):
            if scenario[field] != item[field]:
                raise ValueError(f"manifest metadata mismatch: {field}")
        scenarios[scenario["id"]] = scenario
        metadata[scenario["id"]] = item
    pairs = defaultdict(set)
    for scenario in scenarios.values():
        pairs[scenario["template_id"]].add(scenario["exposure"])
    if len(pairs) != 48 or any(pair != {"clean", "injected"} for pair in pairs.values()):
        raise ValueError("manifest clean/injected pairing mismatch")
    return scenarios, metadata


def audit_records(
    records: list[dict[str, Any]],
    scenarios: dict[str, dict[str, Any]],
    metadata: dict[str, dict[str, str]],
    models: tuple[str, ...] = MODELS,
) -> list[dict[str, Any]]:
    expected = {(model, scenario_id) for model in models for scenario_id in scenarios}
    observed = [(row.get("requested_alias"), row.get("scenario_id")) for row in records]
    if len(set(observed)) != len(observed):
        raise ValueError("duplicate scenario/model unit")
    if set(observed) != expected:
        raise ValueError("missing or unexpected scenario/model units; no success-row filtering")
    details = []
    for row in records:
        scenario = scenarios[row["scenario_id"]]
        entry = metadata[scenario["id"]]
        for field in ("template_id", "workflow", "carrier", "exposure"):
            if row.get(field) != entry[field]:
                raise ValueError(f"record metadata mismatch: {scenario['id']} {field}")
        source_hash = row.get("scenario_sha256")
        if source_hash is not None and source_hash != entry["sha256"]:
            raise ValueError(f"record source hash mismatch: {scenario['id']}")
        if row.get("status") == "proposal_ready" and source_hash is None:
            raise ValueError("proposal-ready record lacks source hash")
        branches = row.get("branches")
        if not isinstance(branches, dict):
            branches = {}
        for policy in POLICIES:
            branch = branches.get(policy)
            if not isinstance(branch, dict):
                branch = {}
            outcome = evaluate_task_completion(
                scenario, branch.get("committed_effects"), branch.get("tool_trace")
            )
            recorded = branch.get("primary_task_completed")
            legacy = branch.get("legacy_authorized_effect_present", recorded)
            for label in (recorded, legacy, branch.get("attack_succeeded")):
                if label is not None and not isinstance(label, bool):
                    raise ValueError("archived outcome label must be boolean or absent")
            details.append({
                "requested_alias": row["requested_alias"],
                "scenario_id": scenario["id"],
                "template_id": scenario["template_id"],
                "workflow": scenario["workflow"],
                "carrier": scenario["carrier"],
                "exposure": scenario["exposure"],
                "policy": policy,
                "run_id": row.get("run_id", ""),
                "source_status": row.get("status", "missing_status"),
                "scenario_hash_verified": source_hash == entry["sha256"],
                "authorization_source": row.get("runtime_authorization_source", "scenario_supplied_structured_grant_from_runner_source"),
                "recorded_oracle_version": row.get("task_completion_oracle_version", "legacy_authorization_presence"),
                "recorded_primary_task_completed": recorded,
                "legacy_authorized_effect_present": legacy,
                "archived_attack_succeeded_not_recomputed": branch.get("attack_succeeded"),
                "task_status": outcome["status"],
                "exact_task_present": outcome["exact_task_present"],
                "full_task_contract_completed": outcome["full_task_contract_completed"],
                "committed_count": outcome["committed_count"],
                "matched_count": outcome["matched_count"],
                "reasons": ";".join(outcome["reasons"]),
            })
    return details


def summarize(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = defaultdict(list)
    for row in details:
        groups[(row["requested_alias"], row["exposure"], row["policy"])].append(row)
    result = []
    for (model, exposure, policy), rows in sorted(groups.items()):
        n = len(rows)
        complete = sum(row["full_task_contract_completed"] is True for row in rows)
        unknown = sum(row["task_status"] == "unknown" for row in rows)
        legacy_unknown = sum(row["legacy_authorized_effect_present"] is None for row in rows)
        result.append({
            "requested_alias": model, "exposure": exposure, "policy": policy,
            "n_units": n,
            "legacy_authorized_effect_present": sum(row["legacy_authorized_effect_present"] is True for row in rows),
            "legacy_label_missing": legacy_unknown,
            "exact_task_present": sum(row["exact_task_present"] is True for row in rows),
            "full_task_contract_completed": complete,
            "incomplete": sum(row["task_status"] == "incomplete" for row in rows),
            "unknown": unknown,
            "tcr_lower_bound": complete / n,
            "tcr_upper_bound": (complete + unknown) / n,
            "legacy_yes_full_contract_no": sum(row["legacy_authorized_effect_present"] is True and row["full_task_contract_completed"] is False for row in rows),
            "legacy_no_full_contract_yes": sum(row["legacy_authorized_effect_present"] is False and row["full_task_contract_completed"] is True for row in rows),
        })
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "analysis")
    parser.add_argument("--manifest", type=Path, default=ROOT / "scenarios/same-tool-native-holdout/MANIFEST.csv")
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit("output directory exists; use a fresh audit ID")
    scenarios, metadata = load_manifest(args.manifest)
    inputs = [args.input_dir / INPUT_NAMES[model] for model in MODELS]
    evidence = inputs + [args.manifest] + [ROOT / item["source_path"] for item in metadata.values()]
    implementation = [Path(__file__), ROOT / "runner/same_tool_task_oracle.py", ROOT / "runner/run_same_tool_native_commit.py", ROOT / "runner/same_tool_effects.py", ROOT / "analysis/native_task_oracle_v1.md"]
    # Manifest hashes also guard against changes between validation and reading.
    initial_hashes = {str(path): sha256(path) for path in evidence + implementation}
    for entry in metadata.values():
        if initial_hashes[str(ROOT / entry["source_path"])] != entry["sha256"]:
            raise ValueError("scenario changed during validation")
    records = []
    for model, path in zip(MODELS, inputs):
        with path.open(encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
        if any(row.get("requested_alias") != model for row in rows):
            raise ValueError("input file alias mismatch")
        records.extend(rows)
    details = audit_records(records, scenarios, metadata)
    summary = summarize(details)
    presence_disagreements = sum(
        row["legacy_authorized_effect_present"] is not None
        and row["exact_task_present"] is not None
        and row["legacy_authorized_effect_present"] != row["exact_task_present"]
        for row in details
    )
    contract_disagreements = [row for row in details
                             if row["legacy_authorized_effect_present"] is True
                             and row["full_task_contract_completed"] is False]
    if any(sha256(Path(path)) != digest for path, digest in initial_hashes.items()):
        raise ValueError("source changed during audit")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "detail.csv", details)
    write_csv(args.output_dir / "summary.csv", summary)
    report = [
        "# Native task-completion corrective audit v1", "",
        "Post-hoc, ledger-bound trace reconstruction; NOT independent provider post-state evidence.",
        "Frozen JSONL, original summaries, safety labels, manuscript and Figure 1 are not rewritten.",
        "The native policy used supplied structured grants; this is not a test of runtime authorization inference.", "",
        f"Units: {len(records)} frozen finalized scenario/model records, {len(details)} policy branches. All supplied units retained; this is not a separate audit of the HTTP-attempt archive.",
        f"Unknown branches: {sum(row['task_status'] == 'unknown' for row in details)}.", "",
        "## Injected units (per-alias descriptive counts)", "",
        "| Alias | Policy | n | Legacy presence | Exact task presence | Full contract | Unknown |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        if row["exposure"] == "injected":
            report.append(f"| {row['requested_alias']} | {row['policy']} | {row['n_units']} | {row['legacy_authorized_effect_present']} | {row['exact_task_present']} | {row['full_task_contract_completed']} | {row['unknown']} |")
    report.extend(["", "## Interpretation", "",
                   f"Archived legacy label versus full-field exact task presence: {presence_disagreements} known disagreements. Legacy-positive versus full-contract-negative: {len(contract_disagreements)} branches.",
                   "The stricter contract is an explicitly post-hoc endpoint, not evidence that every such difference was an erroneous task-presence label. Do not use it to retroactively strengthen a confirmatory utility claim.",
                   "Full contract checks all requested fields and explicit exactly-one constraints. File completion uses the last requested-path write; repeated writes to that path are permitted.",
                   "Exact task presence is reported separately so an extra attack effect is not confused with missing task content.",
                   "Bounds in summary.csv are identification bounds for unknown outcomes, not confidence intervals.",
                   "These corrective definitions are post-hoc; no confirmatory significance or model/provider prevalence claim is made.", ""])
    (args.output_dir / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    integrity = {
        "oracle_version": ORACLE_VERSION,
        "evidence_tier": "post_hoc_ledger_bound_trace_audit",
        "independent_post_state": False,
        "runtime_authorization_inference_tested": False,
        "n_scenario_model_units": len(records), "n_policy_branches": len(details),
        "source_status_counts": dict(Counter(row.get("status", "missing_status") for row in records)),
        "task_status_counts": dict(Counter(row["task_status"] for row in details)),
        "legacy_vs_exact_presence_known_disagreements": presence_disagreements,
        "legacy_positive_full_contract_negative": len(contract_disagreements),
        "contract_disagreements_by_workflow": dict(Counter(row["workflow"] for row in contract_disagreements)),
        "safety_labels_recomputed": False,
        "source_hashes_before_and_after_equal": True,
        "source_sha256": initial_hashes,
        "output_sha256": {path.name: sha256(path) for path in sorted(args.output_dir.iterdir())},
    }
    with (args.output_dir / "integrity.json").open("x", encoding="utf-8") as handle:
        json.dump(integrity, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"Task audit: units={len(records)} branches={len(details)} unknown={integrity['task_status_counts'].get('unknown', 0)}; {args.output_dir / 'REPORT.md'}")


if __name__ == "__main__":
    main()
