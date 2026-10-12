#!/usr/bin/env python3
"""Audit the source-unbound external holdout amendment."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate(payload: dict) -> dict:
    if payload.get("freeze_status") != "design_frozen_source_binding_pending":
        raise ValueError("amendment is not source-binding pending")
    disjoint = payload["source_disjointness"]
    if disjoint["source_bindings"] or disjoint["scheduled_units"] != 0:
        raise ValueError("design audit must not contain execution bindings")
    corpus = payload["corpus_plan"]
    if corpus["attack_templates"] != corpus["templates_per_family"] * len(corpus["attack_families"]):
        raise ValueError("attack template count mismatch")
    if corpus["benign_counterparts"] != corpus["attack_templates"] or corpus["scenario_ids"] != corpus["attack_templates"] * 2:
        raise ValueError("paired corpus count mismatch")
    if payload["planned_units"]["per_model_provider"] != corpus["scenario_ids"] * len(payload["conditions"]):
        raise ValueError("trajectory denominator mismatch")
    if payload["planned_units"]["live_units"] != 0 or not payload["execution_gate"]["no_live_api_in_design_or_audit"]:
        raise ValueError("design unexpectedly schedules live calls")
    if payload["outcomes"]["observer"] != "independent provider post-state observer; local ledger is reconciliation evidence only":
        raise ValueError("independent observer requirement changed")
    return {
        "protocol_id": payload["protocol_id"],
        "attack_templates": corpus["attack_templates"],
        "benign_counterparts": corpus["benign_counterparts"],
        "scenario_ids": corpus["scenario_ids"],
        "per_model_provider_trajectories": payload["planned_units"]["per_model_provider"],
        "scheduled_units": disjoint["scheduled_units"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=ROOT / "analysis/external_holdout_amendment_v1.json")
    args = parser.parse_args()
    payload = json.loads(args.protocol.read_text(encoding="utf-8"))
    summary = validate(payload)
    summary["protocol_sha256"] = hashlib.sha256(args.protocol.read_bytes()).hexdigest()
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
