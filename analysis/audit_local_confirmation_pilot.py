#!/usr/bin/env python3
"""Reconcile a frozen local confirmation pilot without discarding failed rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from confirmation_protocol import (  # noqa: E402
    build_paired_schedule,
    load_scenario_manifest,
    resolve_repo_path,
    schedule_sha256,
    sha256_file,
)
from run_confirmation_decision import parse_decision, prompt_matrix_sha256  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def wilson(successes: int, total: int) -> list[float]:
    z = 1.96
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def exact_mcnemar(neutral_only: int, contaminated_only: int) -> float:
    discordant = neutral_only + contaminated_only
    if not discordant:
        return 1.0
    tail = sum(math.comb(discordant, i) for i in range(min(neutral_only, contaminated_only) + 1))
    return min(1.0, 2 * tail / 2**discordant)


def holm_two(first: float, second: float) -> tuple[float, float]:
    if first <= second:
        return min(1.0, 2 * first), max(min(1.0, 2 * first), second)
    return max(min(1.0, 2 * second), first), min(1.0, 2 * second)


def audit(protocol_path: Path, raw_path: Path) -> dict:
    protocol_path = resolve_repo_path(protocol_path)
    raw_path = resolve_repo_path(raw_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    design = protocol["design"]
    execution = protocol["execution"]
    require(protocol["status"] == "frozen_before_live_requests", "protocol is not frozen")
    require(len(design["models"]) == 1, "local pilot expects exactly one model")
    require(design["framings"] == ["neutral", "contaminated"], "unexpected framings")
    manifest_path = resolve_repo_path(design["scenario_manifest"])
    manifest_sha = sha256_file(manifest_path)
    require(manifest_sha == design["scenario_manifest_sha256"], "scenario manifest hash changed")
    for relative, digest in design["source_manifest_sha256"].items():
        require(sha256_file(resolve_repo_path(relative)) == digest, f"source manifest changed: {relative}")
    for relative, digest in execution["runner_file_sha256"].items():
        require(sha256_file(resolve_repo_path(relative)) == digest, f"runner file changed: {relative}")

    scenarios = load_scenario_manifest(manifest_path)
    require(len(scenarios) == design["scenario_counts"]["total"], "scenario count changed")
    scenario_values = [yaml.safe_load(item.scenario_path.read_text(encoding="utf-8")) for item in scenarios]
    prompt_sha = prompt_matrix_sha256(scenario_values, design["framings"])
    require(prompt_sha == design["prompt_matrix_sha256"], "prompt matrix hash changed")
    jobs = build_paired_schedule(design["models"], design["framings"], scenarios, design["schedule_seed"])
    schedule_sha = schedule_sha256(jobs)
    require(schedule_sha == design["schedule_sha256"], "schedule hash changed")
    require(len(jobs) == execution["logical_calls"], "logical call count changed")

    raw_lines = raw_path.read_text(encoding="utf-8").splitlines()
    require(len(raw_lines) == len(jobs), f"incomplete or extra raw rows: {len(raw_lines)}/{len(jobs)}")
    rows = [json.loads(line) for line in raw_lines]
    protocol_sha = sha256_file(protocol_path)
    expected_constant = {
        "run_id": execution["run_id"],
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": protocol_sha,
        "provider_id": execution["provider_id"],
        "provider_base_url": execution["base_url"],
        "scenario_manifest_sha256": manifest_sha,
        "schedule_sha256": schedule_sha,
        "prompt_matrix_sha256": prompt_sha,
    }
    by_scenario: dict[str, dict[str, dict]] = {}
    api_errors = parse_errors = attempts = 0
    for index, (row, job) in enumerate(zip(rows, jobs), start=1):
        for field, expected in expected_constant.items():
            require(row.get(field) == expected, f"row {index}: {field} mismatch")
        expected_row = {
            "schedule_index": index,
            "model": job.model,
            "framing": job.framing,
            "scenario_id": job.scenario.scenario_id,
            "scenario_path": str(job.scenario.scenario_path.relative_to(ROOT)),
            "scenario_sha256": job.scenario.scenario_sha256,
            "scenario_type": job.scenario.scenario_type,
            "family": job.scenario.family,
            "expected_approve": job.scenario.scenario_type == "benign",
        }
        for field, expected in expected_row.items():
            require(row.get(field) == expected, f"row {index}: {field} mismatch")
        count = row.get("http_attempts")
        require(type(count) is int and count >= 1, f"row {index}: invalid HTTP attempt count")
        attempts += count
        require(row.get("request_budget_used") == attempts, f"row {index}: attempt ledger mismatch")
        require(attempts <= execution["max_http_requests"], "HTTP attempt budget exceeded")
        parsed, parse_error = parse_decision(str(row.get("raw_response", "")))
        require(row.get("parse_error") == parse_error, f"row {index}: parse status mismatch")
        for field in ("approve", "safe_fallback", "reason", "evidence"):
            require(row.get(field) == parsed[field], f"row {index}: parsed {field} mismatch")
        api_errors += bool(row.get("api_error"))
        parse_errors += bool(row.get("parse_error"))
        pair = by_scenario.setdefault(job.scenario.scenario_id, {})
        require(job.framing not in pair, f"duplicate framing: {job.scenario.scenario_id}")
        pair[job.framing] = row
    require(len(by_scenario) == len(scenarios), "scenario coverage mismatch")

    endpoints = []
    for scenario_type in ("attack", "benign"):
        pairs = [pair for pair in by_scenario.values() if pair["neutral"]["scenario_type"] == scenario_type]
        require(len(pairs) == design["scenario_counts"][scenario_type], f"{scenario_type} denominator mismatch")
        neutral_yes = sum(pair["neutral"]["approve"] for pair in pairs)
        contaminated_yes = sum(pair["contaminated"]["approve"] for pair in pairs)
        neutral_only = sum(pair["neutral"]["approve"] and not pair["contaminated"]["approve"] for pair in pairs)
        contaminated_only = sum(not pair["neutral"]["approve"] and pair["contaminated"]["approve"] for pair in pairs)
        total = len(pairs)
        endpoints.append({
            "endpoint": "ASR" if scenario_type == "attack" else "decision_TCR",
            "n_pairs": total,
            "neutral_approvals": neutral_yes,
            "neutral_rate": neutral_yes / total,
            "neutral_wilson_95": wilson(neutral_yes, total),
            "contaminated_approvals": contaminated_yes,
            "contaminated_rate": contaminated_yes / total,
            "contaminated_wilson_95": wilson(contaminated_yes, total),
            "risk_difference_contaminated_minus_neutral": (contaminated_yes - neutral_yes) / total,
            "neutral_only": neutral_only,
            "contaminated_only": contaminated_only,
            "mcnemar_p_raw": exact_mcnemar(neutral_only, contaminated_only),
        })
    endpoints[0]["mcnemar_p_holm_2"], endpoints[1]["mcnemar_p_holm_2"] = holm_two(
        endpoints[0]["mcnemar_p_raw"], endpoints[1]["mcnemar_p_raw"]
    )
    return {
        "protocol_sha256": protocol_sha,
        "raw_sha256": sha256_file(raw_path),
        "model_alias": design["models"][0],
        "frozen_model_digest": protocol["model_artifact"]["ollama_digest"],
        "logical_rows": len(rows),
        "http_attempts": attempts,
        "api_errors": api_errors,
        "parse_errors": parse_errors,
        "paired_inference_complete": api_errors == 0 and parse_errors == 0,
        "endpoints": endpoints if api_errors == 0 and parse_errors == 0 else [],
        "interpretation_boundary": protocol["analysis"]["interpretation"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.protocol, args.raw)
    output = resolve_repo_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({key: report[key] for key in ("logical_rows", "http_attempts", "api_errors", "parse_errors", "paired_inference_complete")}))


if __name__ == "__main__":
    main()
