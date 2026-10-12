#!/usr/bin/env python3
"""Validate the offline external attack-source registry."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SOURCE_FIELDS = {"source_id", "paper_use", "public_role", "planned_split", "psebench_role", "license_status", "raw_content_status", "citation_required"}
REQUIRED_CONVERSION_FIELDS = {"scenario_id", "source_id", "source_item_hash", "attack_family", "attack_method", "split", "workflow", "carrier", "trusted_request", "authorized_arguments", "clean_counterpart_id", "transformation_rationale", "expected_escalation", "license_record", "oracle_owner"}


def validate(payload: dict) -> dict:
    if payload.get("freeze_status") != "offline_registry_only":
        raise ValueError("registry is not offline-only")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("missing sources")
    source_ids = set()
    for source in sources:
        missing = REQUIRED_SOURCE_FIELDS - set(source)
        if missing:
            raise ValueError(f"source missing fields: {sorted(missing)}")
        if source["source_id"] in source_ids:
            raise ValueError("duplicate source_id")
        source_ids.add(source["source_id"])
        if source["license_status"] == "verified" and source["raw_content_status"] == "not_vendored":
            raise ValueError("verified source unexpectedly marked not vendored without content record")
    families = payload.get("attack_families")
    if not isinstance(families, list) or not families:
        raise ValueError("missing attack families")
    family_ids = set()
    for family in families:
        if set(family) != {"family_id", "methods", "source_ids"}:
            raise ValueError("malformed attack family")
        if family["family_id"] in family_ids:
            raise ValueError("duplicate family_id")
        family_ids.add(family["family_id"])
        if not family["methods"] or not set(family["source_ids"]).issubset(source_ids):
            raise ValueError("attack family has invalid source mapping")
    contract = payload.get("conversion_contract", {})
    if set(contract["required_fields"]) != REQUIRED_CONVERSION_FIELDS:
        raise ValueError("conversion contract fields changed")
    if contract.get("oracle_owner") != "PSEBench_grant_relative_scenario_metadata":
        raise ValueError("external source cannot own oracle")
    if not contract.get("independent_observer_required_for_headline"):
        raise ValueError("headline observer requirement missing")
    return {"source_count": len(sources), "family_count": len(families), "source_ids": sorted(source_ids), "family_ids": sorted(family_ids)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=ROOT / "analysis/external_attack_registry_v1.json")
    args = parser.parse_args()
    payload = json.loads(args.registry.read_text(encoding="utf-8"))
    summary = validate(payload)
    summary["registry_sha256"] = hashlib.sha256(args.registry.read_bytes()).hexdigest()
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
