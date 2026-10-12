#!/usr/bin/env python3
"""Summarize one pre-registered same-tool native extension alias.

This wrapper deliberately keeps the primary four-alias summarizer unchanged;
the extension is emitted as a separate descriptive slice with no pooled or
multiplicity-adjusted claim.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
import summarize_same_tool_native_commit as base  # noqa: E402


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"empty output: {path}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def validate(rows: list[dict[str, Any]], alias: str, manifest: Path) -> None:
    if len(rows) != 96:
        raise ValueError(f"expected 96 rows for {alias}, found {len(rows)}")
    keys = {(row.get("requested_alias"), row.get("scenario_id")) for row in rows}
    if len(keys) != 96 or {row["requested_alias"] for row in rows} != {alias}:
        raise ValueError("alias/scenario keys are not unique")
    scenarios = base.load_scenarios(manifest)
    expected_ids = {scenario["id"] for scenario in scenarios}
    if {row["scenario_id"] for row in rows} != expected_ids:
        raise ValueError("extension did not use the frozen 96-row manifest")
    for row in rows:
        if row.get("api_error") or row.get("status") == "infrastructure_failure":
            raise ValueError("extension contains an infrastructure failure")
        if row.get("status") != "proposal_ready":
            raise ValueError(f"non-ready row: {row['scenario_id']}")
        if not row.get("same_tool_first_proposal"):
            raise ValueError(f"same-tool invariant failed: {row['scenario_id']}")
        if set((row.get("branches") or {})) != set(base.POLICIES):
            raise ValueError(f"missing policy branch: {row['scenario_id']}")


def metadata_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = []
    for row in rows:
        for item in row.get("response_metadata") or []:
            model = item.get("response_model")
            if model:
                values.append(str(model))
    return {
        "metadata_rows": len(values),
        "metadata_models": sorted(set(values)),
        "metadata_matches_requested": int(set(values) == {rows[0]["requested_alias"]}),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("final", type=Path)
    parser.add_argument("--alias", required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "scenarios" / "same-tool-native-holdout" / "MANIFEST.csv",
    )
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()
    rows = load(args.final)
    validate(rows, args.alias, args.manifest)

    # Reuse the audited aggregation logic with a one-alias family.
    original_models = base.MODELS
    base.MODELS = (args.alias,)
    try:
        detail = base.details(rows)
        summary = base.summaries(detail)
        paired = base.paired(detail)
        exposure = base.exposure_paired(detail)
        cluster = base.cluster_paired(detail)
        commit_detail = base.commit_details(rows)
        commit_summary = base.commit_summaries(commit_detail)
    finally:
        base.MODELS = original_models

    injected = [row for row in detail if row["exposure"] == "injected"]
    integrity = {
        "protocol": "analysis/native_extension_protocol_v1.md",
        "requested_alias": args.alias,
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "final_sha256": hashlib.sha256(args.final.read_bytes()).hexdigest(),
        "scenario_count": len(rows),
        "paired_template_count": len({row["template_id"] for row in rows}),
        "injected_pair_count": len(injected),
        "proposal_ready": sum(row["proposal_ready"] for row in detail),
        "permissive_attack": sum(row["permissive_attack"] for row in injected),
        "IACG_attack": sum(row["IACG_attack"] for row in injected),
        "permissive_task": sum(row["permissive_task"] for row in injected),
        "IACG_task": sum(row["IACG_task"] for row in injected),
        "metadata": metadata_summary(rows),
        "interpretation": "pre-registered single-relay extension; descriptive, not pooled",
    }
    prefix = args.output_prefix
    write_csv(prefix.with_name(prefix.name + "_detail.csv"), detail)
    write_csv(prefix.with_name(prefix.name + "_summary.csv"), summary)
    write_csv(prefix.with_name(prefix.name + "_paired.csv"), paired)
    write_csv(prefix.with_name(prefix.name + "_exposure_paired.csv"), exposure)
    write_csv(prefix.with_name(prefix.name + "_cluster_paired.csv"), cluster)
    write_csv(prefix.with_name(prefix.name + "_commit_detail.csv"), commit_detail or [{"empty": "1"}])
    write_csv(prefix.with_name(prefix.name + "_commit_summary.csv"), commit_summary or [{"empty": "1"}])
    prefix.with_name(prefix.name + "_integrity.json").write_text(
        json.dumps(integrity, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(integrity, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

