#!/usr/bin/env python3
"""Audit record-level source bindings without treating them as converted attacks."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate(payload: dict) -> dict:
    if payload.get("status") != "source_items_bound_conversion_pending":
        raise ValueError("unexpected binding status")
    if payload.get("raw_prompt_content_in_repo") or payload.get("live_execution_authorized"):
        raise ValueError("manifest stores raw content or authorizes live execution")
    rows = payload.get("item_bindings")
    if not isinstance(rows, list) or len(rows) != 72:
        raise ValueError("expected 72 record-level bindings")
    ids = {row.get("binding_id") for row in rows}
    scenario_ids = {row.get("scenario_id") for row in rows}
    hashes = [row.get("source_item_hash") for row in rows]
    if None in ids or len(ids) != 72 or len(scenario_ids) != 72:
        raise ValueError("binding identifiers are not unique")
    if any(not isinstance(value, str) or len(value) != 64 for value in hashes) or len(set(hashes)) != 72:
        raise ValueError("source item hashes must be unique SHA-256 values")
    if payload.get("scheduled_units") != 0:
        raise ValueError("source binding must not schedule live units")
    roles = Counter(row.get("role") for row in rows)
    if roles != Counter({"attack_source": 36, "benign_counterpart": 36}):
        raise ValueError(f"role counts mismatch: {roles}")
    attack = {row["scenario_id"]: row for row in rows if row["role"] == "attack_source"}
    benign = {row["scenario_id"]: row for row in rows if row["role"] == "benign_counterpart"}
    if set(attack) != {row["clean_counterpart_id"] for row in benign.values()}:
        raise ValueError("attack/benign pairing mismatch")
    if set(benign) != {row["clean_counterpart_id"] for row in attack.values()}:
        raise ValueError("benign/attack pairing mismatch")
    if any(row.get("transformation_status") != "pending" for row in attack.values()):
        raise ValueError("attack transformation is prematurely marked complete")
    if any(row.get("conversion_status") != "pending" for row in rows):
        raise ValueError("conversion is prematurely marked complete")
    source_files = payload.get("source_files", [])
    if {item.get("source_id") for item in source_files} != {"advbench", "alpaca"}:
        raise ValueError("source file inventory mismatch")
    return {
        "manifest_id": payload["manifest_id"],
        "source_files": len(source_files),
        "record_bindings": len(rows),
        "attack_bindings": len(attack),
        "benign_bindings": len(benign),
        "attack_families": dict(Counter(row["attack_family"] for row in attack.values())),
        "scheduled_units": payload["scheduled_units"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "analysis/external_holdout_binding_manifest_v2.json")
    args = parser.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    summary = validate(payload)
    summary["manifest_sha256"] = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
