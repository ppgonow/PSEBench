#!/usr/bin/env python3
"""Independent integrity audit for the frozen confirmation amendment."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
sys.path.insert(0, str(ROOT / "analysis"))

from confirmation_power_analysis import exact_power, wilson  # noqa: E402
from confirmation_protocol import (  # noqa: E402
    build_paired_schedule,
    load_scenario_manifest,
    resolve_repo_path,
    schedule_sha256,
    sha256_file,
)
from run_confirmation_decision import parse_decision, prompt_matrix_sha256  # noqa: E402
from summarize_confirmation_decision import validate_matrix  # noqa: E402


DEFAULT_PROTOCOL = ROOT / "analysis" / "confirmation_amendment_v1.json"
DEFAULT_FREEZE = ROOT / "analysis" / "confirmation_amendment_v1_SHA256.txt"


def fail(message: str) -> None:
    raise SystemExit(message)


def verify_freeze_file(path: Path) -> None:
    entries = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        target = resolve_repo_path(relative)
        actual = sha256_file(target)
        if actual != expected:
            fail(f"freeze hash mismatch: {relative}")
        entries += 1
    if not entries:
        fail("empty confirmation freeze file")


def load_protocol(path: Path) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("schema_version") != 1:
        fail("unsupported confirmation protocol schema")
    if protocol.get("status") != "frozen_before_live_requests":
        fail("confirmation protocol is not frozen-before-live")
    return protocol


def audit_design(protocol: dict) -> tuple[list, list]:
    design = protocol["design"]
    execution = protocol["execution"]
    models = [str(value) for value in design["models"]]
    framings = [str(value) for value in design["framings"]]
    if len(models) != 3 or len(set(models)) != 3:
        fail("amendment must freeze exactly three unique models")
    if framings != ["neutral", "contaminated"]:
        fail("amendment framings must be neutral then contaminated")

    manifest_path = resolve_repo_path(design["scenario_manifest"])
    if sha256_file(manifest_path) != design["scenario_manifest_sha256"]:
        fail("confirmation manifest hash differs from protocol")
    for relative, expected in design["source_manifest_sha256"].items():
        if sha256_file(resolve_repo_path(relative)) != expected:
            fail(f"source manifest hash differs from protocol: {relative}")
    for relative, expected in execution["runner_file_sha256"].items():
        if sha256_file(resolve_repo_path(relative)) != expected:
            fail(f"runner file hash differs from protocol: {relative}")
    scenarios = load_scenario_manifest(manifest_path)
    scenario_documents = [
        yaml.safe_load(row.scenario_path.read_text(encoding="utf-8")) or {}
        for row in scenarios
    ]
    if prompt_matrix_sha256(scenario_documents, framings) != design["prompt_matrix_sha256"]:
        fail("prompt matrix hash differs from protocol")

    expected_counts = design["scenario_counts"]
    counts = Counter(row.scenario_type for row in scenarios)
    if len(scenarios) != int(expected_counts["total"]):
        fail("total scenario count differs from protocol")
    for scenario_type in ("attack", "benign"):
        if counts[scenario_type] != int(expected_counts[scenario_type]):
            fail(f"{scenario_type} scenario count differs from protocol")
        family_counts = Counter(
            row.family for row in scenarios if row.scenario_type == scenario_type
        )
        frozen = expected_counts[f"{scenario_type}_by_family"]
        if family_counts != Counter({key: int(value) for key, value in frozen.items()}):
            fail(f"{scenario_type} family balance differs from protocol")

    jobs = build_paired_schedule(models, framings, scenarios, design["schedule_seed"])
    if schedule_sha256(jobs) != design["schedule_sha256"]:
        fail("schedule hash differs from protocol")
    if len(jobs) != int(execution["logical_calls"]):
        fail("logical-call count differs from protocol")
    if len(jobs) != int(execution["max_logical_calls"]):
        fail("logical-call ceiling is not exact")
    if int(execution["max_http_requests"]) < len(jobs):
        fail("HTTP request budget is smaller than logical matrix")
    if int(execution["sequential_workers"]) != 1:
        fail("confirmation amendment must use one sequential worker")

    positions: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
    scenario_types = {row.scenario_id: row.scenario_type for row in scenarios}
    for index, job in enumerate(jobs, start=1):
        positions[(job.model, job.scenario.scenario_id)].append((index, job.framing))
    framing_first = Counter()
    for (model, scenario_id), pair in positions.items():
        if len(pair) != 2 or pair[1][0] != pair[0][0] + 1:
            fail(f"non-adjacent framing pair: {model}/{scenario_id}")
        if {pair[0][1], pair[1][1]} != {"neutral", "contaminated"}:
            fail(f"invalid framing pair: {model}/{scenario_id}")
        framing_first[(model, scenario_types[scenario_id], pair[0][1])] += 1
    for model in models:
        for scenario_type in ("attack", "benign"):
            if framing_first[(model, scenario_type, "neutral")] != 15:
                fail(f"unbalanced neutral-first order: {model}/{scenario_type}")
            if framing_first[(model, scenario_type, "contaminated")] != 15:
                fail(f"unbalanced contaminated-first order: {model}/{scenario_type}")
    model_positions = Counter()
    for offset in range(0, len(jobs), 2 * len(models)):
        block = jobs[offset : offset + 2 * len(models)]
        scenario_type = block[0].scenario.scenario_type
        for position, job in enumerate(block[::2]):
            model_positions[(scenario_type, job.model, position)] += 1
    for scenario_type in ("attack", "benign"):
        for model in models:
            for position in range(len(models)):
                if model_positions[(scenario_type, model, position)] != 10:
                    fail(f"unbalanced model order: {scenario_type}/{model}/{position}")

    analysis = protocol["analysis"]
    for relative, expected in analysis["analysis_file_sha256"].items():
        if sha256_file(resolve_repo_path(relative)) != expected:
            fail(f"analysis file hash differs from protocol: {relative}")
    power = exact_power(30, 0.3, 0.0, 0.05 / 6)
    if not math.isclose(
        power,
        float(
            analysis[
                "power_at_30_pairs_for_one_way_0.30_shift_alpha_0.05_over_6"
            ]
        ),
    ):
        fail("frozen power value does not reproduce")
    if not math.isclose(wilson(0, 30)[1], float(analysis["zero_of_30_wilson_95_upper"])):
        fail("frozen Wilson precision value does not reproduce")
    return scenarios, jobs


def load_raw(path: Path) -> list[dict]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            fail(f"invalid JSONL at line {line_number}: {error}")
        if not isinstance(row, dict):
            fail(f"non-object JSONL row at line {line_number}")
        rows.append(row)
    if not rows:
        fail("raw confirmation file is empty")
    return rows


def audit_raw(
    protocol: dict,
    scenarios: list,
    jobs: list,
    path: Path,
    protocol_path: Path,
) -> dict[str, int]:
    rows = load_raw(path)
    execution = protocol["execution"]
    design = protocol["design"]
    protocol_hash = sha256_file(protocol_path)
    manifest_hash = design["scenario_manifest_sha256"]
    schedule_hash = design["schedule_sha256"]
    expected = {
        (job.model, job.framing, job.scenario.scenario_id): (index, job)
        for index, job in enumerate(jobs, start=1)
    }
    final: dict[tuple[str, str, str], dict] = {}
    successful = Counter()
    cumulative_attempts = 0
    api_error_rows = 0
    parse_error_rows = 0
    for row_number, row in enumerate(rows, start=1):
        key = (str(row.get("model", "")), str(row.get("framing", "")), str(row.get("scenario_id", "")))
        if key not in expected:
            fail(f"unexpected logical key at raw row {row_number}: {key}")
        schedule_index, job = expected[key]
        fixed_fields = {
            "run_id": execution["run_id"],
            "protocol_id": protocol["protocol_id"],
            "protocol_sha256": protocol_hash,
            "provider_id": execution["provider_id"],
            "provider_base_url": execution["base_url"],
            "scenario_manifest_sha256": manifest_hash,
            "schedule_sha256": schedule_hash,
            "prompt_matrix_sha256": design["prompt_matrix_sha256"],
            "schedule_index": schedule_index,
            "scenario_path": str(job.scenario.scenario_path.relative_to(ROOT)),
            "scenario_sha256": job.scenario.scenario_sha256,
            "scenario_type": job.scenario.scenario_type,
            "family": job.scenario.family,
            "expected_approve": job.scenario.scenario_type == "benign",
        }
        for field, value in fixed_fields.items():
            if row.get(field) != value:
                fail(f"raw row {row_number} has invalid {field}")
        attempts = row.get("http_attempts")
        if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
            fail(f"raw row {row_number} has invalid http_attempts")
        cumulative_attempts += attempts
        if row.get("request_budget_used") != cumulative_attempts:
            fail(f"raw row {row_number} breaks cumulative request accounting")
        attempt_errors = row.get("attempt_errors")
        if not isinstance(attempt_errors, list) or len(attempt_errors) > attempts:
            fail(f"raw row {row_number} has invalid attempt_errors")
        if not isinstance(row.get("response_metadata"), dict):
            fail(f"raw row {row_number} has invalid response_metadata")
        decision, parse_error = parse_decision(str(row.get("raw_response", "")))
        if parse_error != str(row.get("parse_error", "")):
            fail(f"raw row {row_number} parse_error is not reproducible")
        for field in ("approve", "safe_fallback", "reason", "evidence"):
            if decision[field] != row.get(field):
                fail(f"raw row {row_number} parsed {field} mismatch")
        api_error_rows += bool(row.get("api_error"))
        parse_error_rows += bool(row.get("parse_error"))
        if not row.get("api_error") and not row.get("parse_error"):
            successful[key] += 1
        final[key] = row
    if cumulative_attempts > int(execution["max_http_requests"]):
        fail("raw rows exceed frozen HTTP request budget")
    if any(count > 1 for count in successful.values()):
        fail("a logical key has multiple successful rows")
    if set(final) != set(expected):
        fail(f"incomplete final matrix: expected {len(expected)}, found {len(final)}")

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in final.values():
        groups[(str(row["model"]), str(row["framing"]))].append(row)
    try:
        validate_matrix(
            groups,
            expected_models=list(design["models"]),
            expected_framings=list(design["framings"]),
            expected_per_cell=int(design["scenario_counts"]["total"]),
        )
    except ValueError as error:
        fail(str(error))
    return {
        "raw_rows": len(rows),
        "logical_keys": len(final),
        "http_attempts": cumulative_attempts,
        "api_error_rows_retained": api_error_rows,
        "parse_error_rows_retained": parse_error_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--raw", type=Path)
    args = parser.parse_args()

    verify_freeze_file(args.freeze)
    protocol = load_protocol(args.protocol)
    scenarios, jobs = audit_design(protocol)
    summary = {
        "protocol_id": protocol["protocol_id"],
        "scenarios": len(scenarios),
        "logical_calls": len(jobs),
        "schedule_sha256": protocol["design"]["schedule_sha256"],
        "raw_audited": bool(args.raw),
    }
    if args.raw:
        summary.update(audit_raw(protocol, scenarios, jobs, args.raw, args.protocol))
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
