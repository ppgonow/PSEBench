#!/usr/bin/env python3
"""Reconstruct source-item hashes and emit a content-free v3 amendment offline."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
FROZEN_V2_SHA256 = "ddb262e6d72ab198ee1ac5dd384f944e29822982bd6ccfe4414f502ffaa78b96"
FROZEN_REGISTRY_SHA256 = "7329a16fb41a42d56855e1f214d5d6bde795d8e9dcfa4b643330830d6d466f5f"
sys.path.insert(0, str(ROOT / "runner"))
from external_source_provenance import build_manifest, load_pinned_sources, validate_manifest


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output-dir", type=Path)
    mode.add_argument("--audit-dir", type=Path)
    args = parser.parse_args()
    if args.output_dir and args.output_dir.exists():
        raise SystemExit("output exists; use a new amendment directory")
    legacy_path = ROOT / "analysis/external_holdout_binding_manifest_v2.json"
    registry_path = ROOT / "analysis/external_attack_registry_v1.json"
    if sha256(legacy_path) != FROZEN_V2_SHA256 or sha256(registry_path) != FROZEN_REGISTRY_SHA256:
        raise ValueError("frozen source binding or registry changed; require a new amendment")
    protected = [legacy_path, registry_path, Path(__file__), ROOT / "runner/external_source_provenance.py"]
    before = {str(path.relative_to(ROOT)): sha256(path) for path in protected}
    legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    records, inventory = load_pinned_sources(args.cache_dir)
    if args.audit_dir:
        payload = json.loads((args.audit_dir / "manifest.json").read_text(encoding="utf-8"))
        integrity = json.loads((args.audit_dir / "integrity.json").read_text(encoding="utf-8"))
        if integrity["input_sha256"] != before:
            raise ValueError("audit implementation or input changed; create a new amendment")
        for name, digest in integrity["output_sha256"].items():
            if sha256(args.audit_dir / name) != digest:
                raise ValueError("audit output hash mismatch")
        summary = validate_manifest(payload, records, inventory, legacy, registry)
    else:
        payload = build_manifest(legacy, records, inventory, registry)
        summary = validate_manifest(payload, records, inventory, legacy, registry)
        args.output_dir.mkdir(parents=True, exist_ok=False)
        with (args.output_dir / "manifest.json").open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        report = (
            "# External source-binding corrective amendment v3\n\n"
            "Three pinned snapshots and all 108 record hashes were verified against cached source bytes. "
            "No raw prompts are included. The original v2 file is unchanged.\n\n"
            "## Corrected scope\n\n"
            "These 36 AdvBench harmful-goal records and 36 Alpaca candidate control-language records "
            "are development seeds, consistent with the source registry. They are not a completed "
            "external holdout or 36 implemented jailbreak attacks. Six family names in v2 were only "
            "planned transformations; zero attack methods have been executed.\n\n"
            "Donor association is not a clean/attack pair until both scenarios share a verified trusted "
            "request and grant. Alpaca safety screening and tool-attack conversion remain pending.\n\n"
            "## Real in-the-wild source pool\n\n"
            "The pinned verazuo/jailbreak_llms snapshot matches the Shen et al. paper cited by JBShield. "
            "36 real upstream jailbreak records were selected from 1,405 rows by sorted normalized "
            "prompt-group hash, one record per exact normalized group, without using model outcomes. "
            "They are source candidates, not converted tool attacks or completed live scenarios. "
            "Only one actual upstream attack family is represented. Their text-group hashes do not "
            "overlap the 72 development donors; this does not prove semantic, historical, or "
            "model-training disjointness. Community cluster hashes are retained.\n\n"
            "Selection was the legacy first 36 records per source, not a random/representative sample. "
            "Historical split disjointness and model training exposure have not been established.\n\n"
            "## Offline rerun\n\n"
            "Run `python3 -B analysis/prepare_external_source_binding_v3.py --cache-dir "
            "<outside-repository-cache> --audit-dir <this-directory>`. Use the three pinned download URLs "
            "in manifest.json, not a moving main branch. The CLI has no network or model-API code.\n\n"
            "Initial download timestamps were not captured at intake; they remain unknown. "
            "The integrity record stores the timestamp of this verification, not a fabricated retrieval time.\n"
        )
        with (args.output_dir / "REPORT.md").open("x", encoding="utf-8") as handle:
            handle.write(report)
        integrity = {
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
            "verification": summary, "input_sha256": before,
            "output_sha256": {name: sha256(args.output_dir / name) for name in ("manifest.json", "REPORT.md")},
        }
        with (args.output_dir / "integrity.json").open("x", encoding="utf-8") as handle:
            json.dump(integrity, handle, indent=2, sort_keys=True)
            handle.write("\n")
    if before != {str(path.relative_to(ROOT)): sha256(path) for path in protected}:
        raise ValueError("protected source or implementation changed during audit")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
