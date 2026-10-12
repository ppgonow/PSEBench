#!/usr/bin/env python3
"""Frozen-manifest loading and paired scheduling for confirmation studies."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import pathlib
from typing import Sequence

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ScenarioManifestRow:
    scenario_id: str
    scenario_path: pathlib.Path
    scenario_type: str
    family: str
    source_manifest: pathlib.Path
    scenario_sha256: str


@dataclass(frozen=True)
class ScheduledJob:
    model: str
    framing: str
    scenario: ScenarioManifestRow


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_repo_path(value: str | pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(value)
    resolved = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as error:
        raise ValueError(f"path escapes repository root: {value}") from error
    return resolved


def _source_hashes(path: pathlib.Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or not {"id", "sha256"}.issubset(rows[0]):
        raise ValueError(f"invalid source manifest: {path}")
    hashes = {str(row["id"]): str(row["sha256"]) for row in rows}
    if len(hashes) != len(rows):
        raise ValueError(f"duplicate scenario IDs in source manifest: {path}")
    return hashes


def load_scenario_manifest(path: pathlib.Path) -> list[ScenarioManifestRow]:
    manifest_path = resolve_repo_path(path)
    with manifest_path.open(newline="", encoding="utf-8") as handle:
        raw_rows = list(csv.DictReader(handle))
    required = {
        "scenario_id",
        "scenario_path",
        "scenario_type",
        "family",
        "source_manifest",
    }
    if not raw_rows or not required.issubset(raw_rows[0]):
        raise ValueError(f"invalid confirmation manifest columns: {manifest_path}")

    source_cache: dict[pathlib.Path, dict[str, str]] = {}
    rows: list[ScenarioManifestRow] = []
    seen_ids: set[str] = set()
    for raw in raw_rows:
        scenario_id = str(raw["scenario_id"])
        if not scenario_id or scenario_id in seen_ids:
            raise ValueError(f"duplicate or empty scenario ID: {scenario_id!r}")
        seen_ids.add(scenario_id)
        scenario_path = resolve_repo_path(str(raw["scenario_path"]))
        source_manifest = resolve_repo_path(str(raw["source_manifest"]))
        if source_manifest not in source_cache:
            source_cache[source_manifest] = _source_hashes(source_manifest)
        source_hashes = source_cache[source_manifest]
        if scenario_id not in source_hashes:
            raise ValueError(f"{scenario_id} is absent from {source_manifest}")
        scenario_sha256 = sha256_file(scenario_path)
        if scenario_sha256 != source_hashes[scenario_id]:
            raise ValueError(f"scenario hash mismatch: {scenario_id}")
        scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8")) or {}
        expected = {
            "id": scenario_id,
            "type": str(raw["scenario_type"]),
            "family": str(raw["family"]),
        }
        for field, value in expected.items():
            if str(scenario.get(field, "")) != value:
                raise ValueError(
                    f"scenario {scenario_id} {field} mismatch: "
                    f"manifest={value!r} yaml={scenario.get(field, '')!r}"
                )
        rows.append(
            ScenarioManifestRow(
                scenario_id=scenario_id,
                scenario_path=scenario_path,
                scenario_type=str(raw["scenario_type"]),
                family=str(raw["family"]),
                source_manifest=source_manifest,
                scenario_sha256=scenario_sha256,
            )
        )
    return rows


def build_paired_schedule(
    models: Sequence[str],
    framings: Sequence[str],
    scenarios: Sequence[ScenarioManifestRow],
    seed: str,
) -> list[ScheduledJob]:
    if len(set(models)) != len(models) or not models:
        raise ValueError("models must be nonempty and unique")
    if set(framings) != {"neutral", "contaminated"} or len(framings) != 2:
        raise ValueError("paired schedule requires neutral and contaminated exactly once")
    if not seed:
        raise ValueError("paired schedule seed must be nonempty")

    ordered = sorted(
        scenarios,
        key=lambda row: hashlib.sha256(
            f"{seed}\0scenario\0{row.scenario_id}".encode("utf-8")
        ).hexdigest(),
    )
    endpoint_rank = {"attack": 0, "benign": 0}
    endpoint_offset = {"attack": 0, "benign": 1}
    model_indices = {model: index for index, model in enumerate(models)}
    jobs: list[ScheduledJob] = []
    for scenario in ordered:
        if scenario.scenario_type not in endpoint_rank:
            raise ValueError(f"unsupported scenario type: {scenario.scenario_type}")
        rank = endpoint_rank[scenario.scenario_type]
        endpoint_rank[scenario.scenario_type] += 1
        offset = (rank + endpoint_offset[scenario.scenario_type]) % len(models)
        model_order = list(models[offset:]) + list(models[:offset])
        for model in model_order:
            neutral_first = (rank + model_indices[model]) % 2 == 0
            framing_order = (
                ("neutral", "contaminated")
                if neutral_first
                else ("contaminated", "neutral")
            )
            jobs.extend(ScheduledJob(model, framing, scenario) for framing in framing_order)
    return jobs


def schedule_sha256(jobs: Sequence[ScheduledJob]) -> str:
    digest = hashlib.sha256()
    for index, job in enumerate(jobs, start=1):
        digest.update(
            f"{index},{job.model},{job.framing},{job.scenario.scenario_id}\n".encode(
                "utf-8"
            )
        )
    return digest.hexdigest()
