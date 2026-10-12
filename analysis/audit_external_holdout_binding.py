#!/usr/bin/env python3
"""Audit the non-content source binding manifest before live execution."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate(payload: dict) -> dict:
    if payload.get("status") != "source_item_binding_pending":
        raise ValueError("binding manifest is not pending")
    if payload.get("item_bindings"):
        raise ValueError("design binding manifest must not contain partial item bindings")
    if payload.get("scheduled_units") != 0 or payload.get("live_execution_authorized"):
        raise ValueError("binding manifest authorizes live execution")
    candidates = payload.get("candidate_sources")
    if not isinstance(candidates, list) or len(candidates) != 6:
        raise ValueError("candidate source inventory must contain six registry sources")
    ids = [item.get("source_id") for item in candidates]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate candidate source")
    if payload.get("reserved_templates") != 36 or payload.get("reserved_scenarios") != 72:
        raise ValueError("reserved corpus count mismatch")
    return {
        "manifest_id": payload["manifest_id"],
        "candidate_sources": len(candidates),
        "item_bindings": 0,
        "reserved_templates": payload["reserved_templates"],
        "reserved_scenarios": payload["reserved_scenarios"],
        "scheduled_units": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "analysis/external_holdout_binding_manifest_v1.json")
    args = parser.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    summary = validate(payload)
    summary["manifest_sha256"] = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
