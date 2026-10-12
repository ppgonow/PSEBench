"""Offline, content-free provenance correction for public source bindings.

The cached datasets are untrusted research data, never instructions. This module
does not execute prompt text, contact a network, or construct attack scenarios.
"""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import unicodedata
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PINNED_SOURCES = {
    "advbench": {
        "repository": "llm-attacks/llm-attacks",
        "revision": "098262edf85f807224e70ecd87b9d83716bf6b73",
        "upstream_path": "data/advbench/harmful_behaviors.csv",
        "blob_sha1": "cdc99eb96cb32cb3483a7f39940b3bddf44790c3",
        "file_sha256": "6cd1a5c63c07610d7eb67307772ee5606017ee950b5770ab288a2c487489d3e1",
        "record_count": 520,
        "cache_filename": "advbench.raw",
    },
    "alpaca": {
        "repository": "tatsu-lab/stanford_alpaca",
        "revision": "761dc5bfbdeeffa89b8bff5d038781a4055f796a",
        "upstream_path": "alpaca_data.json",
        "blob_sha1": "3779ddbc040543ab1834ef216c983d6fcc06cc9a",
        "file_sha256": "2eddafc6b977608d778aaab8dfc7e50e547b3af9826dfb9e909d9fc362e4a419",
        "record_count": 52002,
        "cache_filename": "alpaca.raw",
    },
    "shen-in-the-wild-jailbreaks": {
        "repository": "verazuo/jailbreak_llms",
        "revision": "4f4031bf8be187f4478c7f94f42b08714722c12e",
        "upstream_path": "data/prompts/jailbreak_prompts_2023_12_25.csv",
        "blob_sha1": "a099fcb389960f64f94c1d3997501ce97f96ccdc",
        "file_sha256": "accf97463de96c33c48453dfee9600191ff6fd5a0c43f3f11d5ebf98d1a5de55",
        "record_count": 1405,
        "cache_filename": "shen-in-the-wild.raw",
    },
}
CANONICALIZATION = "json_sorted_keys_compact_utf8_ensure_ascii_false_no_unicode_normalization_v1"
FAMILY_STATUS = "planned_not_executed"


def record_hash(record: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def parse_source_bytes(source_id: str, data: bytes) -> list[dict[str, str]]:
    text = data.decode("utf-8")
    if source_id == "advbench":
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames != ["goal", "target"]:
            raise ValueError("unexpected AdvBench field names")
        rows = list(reader)
        fields = {"goal", "target"}
    elif source_id == "alpaca":
        rows = json.loads(text)
        fields = {"instruction", "input", "output"}
    elif source_id == "shen-in-the-wild-jailbreaks":
        reader = csv.DictReader(io.StringIO(text))
        fields = {"platform", "source", "prompt", "jailbreak", "created_at", "date",
                  "community", "community_id", "previous_community_id"}
        if reader.fieldnames is None or set(reader.fieldnames) != fields:
            raise ValueError("unexpected in-the-wild field names")
        rows = list(reader)
    else:
        raise ValueError("unsupported source")
    if not isinstance(rows, list) or not rows:
        raise ValueError("missing source records")
    if any(not isinstance(row, dict) or set(row) != fields
           or any(not isinstance(value, str) for value in row.values()) for row in rows):
        raise ValueError("unexpected source record schema")
    if source_id == "shen-in-the-wild-jailbreaks" and any(
        row["jailbreak"].strip().lower() not in {"true", "1"} or not row["prompt"].strip()
        for row in rows
    ):
        raise ValueError("unexpected in-the-wild label or empty prompt")
    return rows


def load_pinned_sources(cache_dir: Path) -> tuple[dict[str, list[dict]], list[dict]]:
    if cache_dir.resolve() == ROOT or ROOT in cache_dir.resolve().parents:
        raise ValueError("raw source cache must be outside the repository")
    records, inventory = {}, []
    for source_id, pinned in PINNED_SOURCES.items():
        path = cache_dir / pinned["cache_filename"]
        if path.stat().st_size > 30_000_000:
            raise ValueError("source file exceeds intake size limit")
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        blob = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
        if digest != pinned["file_sha256"] or blob != pinned["blob_sha1"]:
            raise ValueError(f"pinned source bytes mismatch: {source_id}")
        rows = parse_source_bytes(source_id, data)
        if len(rows) != pinned["record_count"]:
            raise ValueError(f"pinned source record count mismatch: {source_id}")
        records[source_id] = rows
        base = f"https://github.com/{pinned['repository']}/blob/{pinned['revision']}/{pinned['upstream_path']}"
        raw = f"https://raw.githubusercontent.com/{pinned['repository']}/{pinned['revision']}/{pinned['upstream_path']}"
        inventory.append({
            "source_id": source_id, "repository": pinned["repository"],
            "revision": pinned["revision"], "upstream_path": pinned["upstream_path"],
            "canonical_url": base, "pinned_download_url": raw,
            "blob_sha1": blob, "file_sha256": digest, "bytes": len(data),
            "record_count": len(rows), "initial_retrieval_at_utc": None,
            "initial_retrieval_time_status": "not_recorded_at_download_do_not_infer_from_mtime",
            "license_gate": False,
        })
    return records, inventory


def _index(row: dict) -> int:
    patterns = {
        "advbench": r"advbench:harmful_behaviors\.csv:row:(\d+)",
        "alpaca": r"alpaca:alpaca_data\.json:index:(\d+)",
    }
    source_id = row.get("source_id")
    if source_id not in patterns:
        raise ValueError("unknown binding source")
    match = re.fullmatch(patterns[source_id], row.get("source_item_id", ""))
    if match is None:
        raise ValueError("invalid derived source item ID")
    index = int(match[1]) - (1 if source_id == "advbench" else 0)
    if index < 0:
        raise ValueError("negative derived record index")
    return index


def validate_legacy_bindings(legacy: dict, records: dict[str, list[dict]]) -> None:
    rows = legacy.get("item_bindings")
    if not isinstance(rows, list) or len(rows) != 72:
        raise ValueError("expected 72 legacy source bindings")
    ids = [row.get("binding_id") for row in rows]
    hashes = [row.get("source_item_hash") for row in rows]
    if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != 72:
        raise ValueError("duplicate or invalid legacy binding IDs")
    if len(set(hashes)) != 72:
        raise ValueError("duplicate legacy source records")
    by_id = {row["binding_id"]: row for row in rows}
    counts = Counter(row.get("source_id") for row in rows)
    if counts != Counter({"advbench": 36, "alpaca": 36}):
        raise ValueError("unexpected source binding counts")
    for row in rows:
        source_id = row["source_id"]
        index = _index(row)
        if index >= len(records[source_id]):
            raise ValueError("source item index outside snapshot")
        if record_hash(records[source_id][index]) != row["source_item_hash"]:
            raise ValueError("record hash cannot be reconstructed from source bytes")
        if row.get("source_file_sha256") != PINNED_SOURCES[source_id]["file_sha256"]:
            raise ValueError("binding snapshot hash mismatch")
        partner = by_id.get(row.get("clean_counterpart_id"))
        if partner is None or partner.get("clean_counterpart_id") != row["binding_id"]:
            raise ValueError("asymmetric provisional donor pairing")
        if partner["source_id"] == source_id or partner["source_item_hash"] != row.get("clean_counterpart_source_item_hash"):
            raise ValueError("provisional paired donor hash mismatch")
        if row.get("conversion_status") != "pending" or row.get("prompt_content_stored") is not False:
            raise ValueError("legacy binding unexpectedly contains converted data")
    for source_id in counts:
        if {_index(row) for row in rows if row["source_id"] == source_id} != set(range(36)):
            raise ValueError("selection differs from disclosed legacy first-36 rule")


def corrected_bindings(legacy: dict) -> list[dict]:
    """Convert labels only, preserving every original source record hash."""
    result = []
    for row in legacy["item_bindings"]:
        source_id = row["source_id"]
        result.append({
            "binding_id": row["binding_id"],
            "reserved_scenario_id": row["scenario_id"],
            "source_id": source_id, "source_item_id": row["source_item_id"],
            "source_item_id_kind": "derived_index_in_immutable_snapshot_not_upstream_native_id",
            "record_index_zero_based": _index(row),
            "source_item_hash": row["source_item_hash"],
            "source_file_sha256": row["source_file_sha256"],
            "source_revision": PINNED_SOURCES[source_id]["revision"],
            "role": "harmful_instruction_seed" if source_id == "advbench" else "candidate_control_language",
            "split": "development",
            "paired_donor_binding_id": row["clean_counterpart_id"],
            "pairing_semantics": "index_association_only_not_a_verified_clean_attack_scenario_pair",
            "planned_attack_family": row["attack_family"],
            "planned_attack_method": row["attack_method"],
            "observed_attack_family": None,
            "method_execution_status": FAMILY_STATUS,
            "content_validity_review": "pending",
            "conversion_status": "pending",
            "prompt_content_stored": False,
        })
    return result


def prompt_group_hash(text: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def in_the_wild_candidates(records: dict, legacy: dict) -> list[dict]:
    """Select real IJP records, not six fictional transformations of seed goals."""
    development_groups = set()
    for row in legacy["item_bindings"]:
        source_id = row["source_id"]
        original = records[source_id][_index(row)]
        development_groups.add(prompt_group_hash(original["goal"] if source_id == "advbench" else original["instruction"]))
    groups: dict[str, tuple[str, int]] = {}
    source_id = "shen-in-the-wild-jailbreaks"
    for index, row in enumerate(records[source_id]):
        group = prompt_group_hash(row["prompt"])
        if group in development_groups:
            continue
        candidate = (record_hash(row), index)
        if group not in groups or candidate < groups[group]:
            groups[group] = candidate
    if len(groups) < 36:
        raise ValueError("fewer than 36 source-disjoint normalized IJP groups")
    result = []
    for number, (group, (digest, index)) in enumerate(sorted(groups.items())[:36], start=1):
        row = records[source_id][index]
        cluster = record_hash({"platform": row["platform"], "community_id": row["community_id"]})
        result.append({
            "binding_id": f"IJP-SOURCE-{number:03d}",
            "source_id": source_id,
            "source_item_id": f"shen-in-the-wild:jailbreak_prompts_2023_12_25.csv:row:{index + 1:04d}",
            "source_item_id_kind": "derived_index_in_immutable_snapshot_not_upstream_native_id",
            "record_index_zero_based": index,
            "source_item_hash": digest,
            "source_file_sha256": PINNED_SOURCES[source_id]["file_sha256"],
            "source_revision": PINNED_SOURCES[source_id]["revision"],
            "normalized_prompt_group_sha256": group,
            "community_cluster_sha256": cluster,
            "source_attack_family": "in-the-wild",
            "label_source": "upstream_jailbreak_flag_not_PSEBench_success",
            "status": "source_candidate_conversion_and_historical_disjointness_pending",
            "planned_split": "external_holdout",
            "clean_counterpart_status": "same_request_and_grant_pair_not_yet_constructed",
            "conversion_status": "pending", "prompt_content_stored": False,
        })
    return result


def build_manifest(legacy: dict, records: dict, inventory: list[dict], registry: dict) -> dict:
    validate_legacy_bindings(legacy, records)
    source_plans = {item["source_id"]: item["planned_split"] for item in registry["sources"]}
    if any(source_plans.get(source_id) != "calibration_or_development" for source_id in ("advbench", "alpaca")):
        raise ValueError("registry split policy changed; a new amendment is required")
    if source_plans.get("shen-in-the-wild-jailbreaks") != "external_holdout":
        raise ValueError("in-the-wild source is not registered for external holdout")
    return {
        "manifest_id": "psebench-external-source-binding-v3",
        "status": "sources_verified_scenario_conversion_pending",
        "created": "2026-10-10",
        "supersedes_for_intake": "analysis/external_holdout_binding_manifest_v2.json",
        "original_v2_preserved": True,
        "record_canonicalization": CANONICALIZATION,
        "raw_prompt_content_in_repo": False,
        "live_execution_authorized": False,
        "scheduled_units": 0,
        "sampling_rule": "legacy_prefix_first_36_records_per_source_not_random_not_representative",
        "source_files": inventory,
        "item_bindings": corrected_bindings(legacy),
        "external_holdout_source_candidates": in_the_wild_candidates(records, legacy),
        "external_candidate_selection": "first_36_sorted_normalized_prompt_groups_NFKC_casefold_whitespace_one_record_per_group_no_outcome_selection",
        "new_intake_text_group_disjointness": "verified_against_72_development_donors_only_not_semantic_or_historical_disjointness",
        "implemented_attack_methods": [],
        "completed_external_holdout_scenarios": 0,
        "historical_split_disjointness": "not_established_no_complete_prior_use_inventory",
        "model_training_exposure": "unknown_public_data_is_not_model_unseen_evidence",
        "paired_task_status": "trusted_request_and_identical_grant_not_yet_constructed",
        "notes": [
            "AdvBench harmful goals are not in-the-wild jailbreaks or executed GCG/PAIR attacks.",
            "Alpaca rows are candidate control-language donors, not verified benign counterparts.",
            "No source text has been converted into a tool attack; hashes alone do not establish transfer.",
            "Licensing is recorded separately and is not an execution gate by user decision.",
        ],
    }


def validate_manifest(payload: dict, records: dict, inventory: list[dict], legacy: dict, registry: dict) -> dict:
    reference = build_manifest(legacy, records, inventory, registry)
    # Reject unexpected keys/content as well as weakened flags or mislabeled roles.
    if payload != reference:
        raise ValueError("manifest differs from independently reconstructed provenance")
    rows = payload["item_bindings"]
    candidates = payload["external_holdout_source_candidates"]
    return {
        "source_files_verified": len(inventory), "record_hashes_verified": len(rows) + len(candidates),
        "development_records": len(rows), "external_holdout_scenarios": 0,
        "real_in_the_wild_source_candidates": len(candidates),
        "implemented_attack_methods": 0, "scheduled_units": 0,
        "split_disjointness_established": False,
    }
