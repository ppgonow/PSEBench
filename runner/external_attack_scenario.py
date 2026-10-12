"""Validate source-attributed external attack scenarios without fetching data."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


ALLOWED_SPLITS = {"calibration", "development", "external_holdout", "adaptive_holdout", "taxonomy_only"}
ALLOWED_CARRIERS = {"message", "retrieved-document", "tool-output"}
ALLOWED_ESCALATIONS = {"persistence", "scope", "target", "sequence", "mixed"}
REQUIRED = {
    "scenario_id", "source_id", "source_item_hash", "attack_family", "attack_method",
    "split", "workflow", "carrier", "trusted_request", "authorized_arguments",
    "clean_counterpart_id", "transformation_rationale", "expected_escalation",
    "license_record", "oracle_owner",
}


def validate_scenario(row: dict[str, Any], known_sources: set[str]) -> None:
    missing = REQUIRED - set(row)
    if missing:
        raise ValueError(f"missing conversion fields: {sorted(missing)}")
    if not isinstance(row["scenario_id"], str) or not row["scenario_id"]:
        raise ValueError("scenario_id must be nonempty")
    if row["source_id"] not in known_sources:
        raise ValueError("unknown source_id")
    source_hash = row["source_item_hash"]
    if not isinstance(source_hash, str) or len(source_hash) != 64 or any(c not in "0123456789abcdef" for c in source_hash.lower()):
        raise ValueError("source_item_hash must be a SHA-256 hex digest")
    if row["split"] not in ALLOWED_SPLITS:
        raise ValueError("invalid split")
    if row["carrier"] not in ALLOWED_CARRIERS:
        raise ValueError("invalid carrier")
    if row["expected_escalation"] not in ALLOWED_ESCALATIONS:
        raise ValueError("invalid escalation")
    if row["oracle_owner"] != "PSEBench_grant_relative_scenario_metadata":
        raise ValueError("external source cannot own oracle")
    if not isinstance(row["trusted_request"], str) or not row["trusted_request"].strip():
        raise ValueError("trusted_request must be explicit")
    if not isinstance(row["authorized_arguments"], dict) or not row["authorized_arguments"]:
        raise ValueError("authorized_arguments must be structured")
    if not isinstance(row["transformation_rationale"], str) or not row["transformation_rationale"].strip():
        raise ValueError("transformation rationale required")
    if not isinstance(row["license_record"], dict) or not row["license_record"].get("status"):
        raise ValueError("license record required")
    # The project does not use licensing as an execution gate. Preserve the
    # record for provenance, but do not mislabel an unresolved status as
    # verified and do not redistribute raw source content by default.


def validate_collection(rows: Iterable[dict[str, Any]], known_sources: set[str]) -> dict[str, Any]:
    rows = list(rows)
    if not rows:
        raise ValueError("empty conversion collection")
    ids: set[str] = set()
    clean_by_id: dict[str, str] = {}
    source_hashes_by_split: dict[str, set[str]] = {}
    for row in rows:
        validate_scenario(row, known_sources)
        if row["scenario_id"] in ids:
            raise ValueError("duplicate scenario_id")
        ids.add(row["scenario_id"])
        clean_by_id[row["scenario_id"]] = row["clean_counterpart_id"]
        source_hashes_by_split.setdefault(row["split"], set()).add(row["source_item_hash"])
    for row in rows:
        if row["clean_counterpart_id"] not in ids:
            raise ValueError("clean counterpart missing from collection")
        if row["clean_counterpart_id"] == row["scenario_id"]:
            raise ValueError("scenario cannot be its own clean counterpart")
    splits = list(source_hashes_by_split)
    for i, left in enumerate(splits):
        for right in splits[i + 1:]:
            overlap = source_hashes_by_split[left] & source_hashes_by_split[right]
            if overlap:
                raise ValueError(f"source item reused across splits: {sorted(overlap)[:1]}")
    return {"scenario_count": len(rows), "split_counts": {split: sum(row["split"] == split for row in rows) for split in sorted(source_hashes_by_split)}, "source_item_count": len({row["source_item_hash"] for row in rows})}


def source_record_hash(record: dict[str, Any]) -> str:
    """Hash a local source record without storing its potentially sensitive text."""
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()
