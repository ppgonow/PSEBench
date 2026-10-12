#!/usr/bin/env python3
"""Audit a frozen synthetic provider-state corpus against N and O.

This audit is evidence for the bounded adapter/observer assumption (A1), not
an assertion that arbitrary provider APIs expose complete post-state fields.
The candidate normalizer and post-state observer are separate implementations.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from same_tool_effects import normalize_call  # noqa: E402
from same_tool_observer import observe_post_state  # noqa: E402


EXPECTED_PROFILES = (
    "canonical-whitespace",
    "canonical-timezone-or-path",
    "candidate-poststate-match",
    "exact-substitution",
    "provider-default",
    "unknown-security-field",
    "partial-update-full-safe",
    "partial-update-full-unsafe",
    "partial-update-incomplete",
    "alternate-endpoint",
    "aggregate-within-budget",
    "aggregate-over-budget",
)
WORKFLOWS = ("reminder", "file", "calendar", "message")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: pathlib.Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _single_row(case: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_call(case["tool_name"], case["candidate"])
    observed = observe_post_state(case["tool_name"], case["post_state"])
    expected = str(case["expected"])
    matched = int(observed.effect == normalized.effect)
    if expected == "same":
        passed = observed.decision == "observed" and bool(matched)
        relation = "same" if matched else "different"
    elif expected == "mismatch":
        passed = observed.decision == "observed" and not matched
        relation = "different" if not matched else "same"
    elif expected == "review":
        passed = observed.decision == "review"
        relation = "review"
    else:
        raise ValueError(f"unsupported single-call expected relation: {expected}")
    return {
        "case_id": case["case_id"],
        "workflow": case["workflow"],
        "profile": case["profile"],
        "expected": expected,
        "case_kind": "single",
        "normalizer_decision": "normalized",
        "observer_decision": observed.decision,
        "observed_relation": relation,
        "effect_match": matched,
        "candidate_digest": normalized.effect.effect_digest or "",
        "observed_digest": observed.effect.effect_digest if observed.effect else "",
        "observed_count": 1 if observed.effect else 0,
        "max_commits": "",
        "passed": int(passed),
        "reason": observed.reason,
    }


def _aggregate_row(case: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        normalize_call(case["tool_name"], arguments)
        for arguments in case["candidate_calls"]
    ]
    observed = [
        observe_post_state(case["tool_name"], post_state)
        for post_state in case["post_states"]
    ]
    all_observed = all(result.decision == "observed" for result in observed)
    matched = all_observed and len(candidates) == len(observed) and all(
        candidate.effect == result.effect for candidate, result in zip(candidates, observed)
    )
    budget = int(case["max_commits"])
    if not matched:
        observed_outcome = "observer-mismatch"
    elif len(observed) <= budget:
        observed_outcome = "aggregate-allow"
    else:
        observed_outcome = "aggregate-budget-block"
    expected = str(case["expected"])
    passed = observed_outcome == expected
    return {
        "case_id": case["case_id"],
        "workflow": case["workflow"],
        "profile": case["profile"],
        "expected": expected,
        "case_kind": "aggregate",
        "normalizer_decision": "normalized" if candidates else "none",
        "observer_decision": "observed" if all_observed else "review",
        "observed_relation": observed_outcome,
        "effect_match": int(matched),
        "candidate_digest": "|".join(candidate.effect.effect_digest or "" for candidate in candidates),
        "observed_digest": "|".join(
            result.effect.effect_digest if result.effect else "" for result in observed
        ),
        "observed_count": len([result for result in observed if result.effect]),
        "max_commits": budget,
        "passed": int(passed),
        "reason": "all observed effects match candidates" if matched else "; ".join(
            result.reason for result in observed
        ),
    }


def audit_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        if "candidate_calls" in case:
            rows.append(_aggregate_row(case))
        else:
            rows.append(_single_row(case))
    return rows


def summarize(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(str(row[field]) for field in fields)].append(row)
    output: list[dict[str, Any]] = []
    for values, selected in sorted(groups.items()):
        summary = dict(zip(fields, values))
        summary.update(
            {
                "cases": len(selected),
                "passed": sum(int(row["passed"]) for row in selected),
                "failures": sum(not int(row["passed"]) for row in selected),
                "same_effect": sum(row["observed_relation"] == "same" for row in selected),
                "mismatch_detected": sum(
                    row["observed_relation"] == "different" for row in selected
                ),
                "review": sum(row["observer_decision"] == "review" for row in selected),
                "aggregate_allow": sum(
                    row["observed_relation"] == "aggregate-allow" for row in selected
                ),
                "aggregate_budget_block": sum(
                    row["observed_relation"] == "aggregate-budget-block"
                    for row in selected
                ),
            }
        )
        output.append(summary)
    return output


def corpus_checks(corpus: dict[str, Any], corpus_path: pathlib.Path) -> dict[str, Any]:
    cases = corpus.get("cases")
    if not isinstance(cases, list):
        raise ValueError("corpus cases must be a list")
    ids = [str(case.get("case_id", "")) for case in cases]
    profiles = Counter(str(case.get("profile", "")) for case in cases)
    workflows = Counter(str(case.get("workflow", "")) for case in cases)
    legacy = json.loads(
        (ROOT / "scenarios" / "same-tool-normalization" / "conformance.json").read_text(
            encoding="utf-8"
        )
    )
    legacy_ids = {str(row["pair_id"]) for row in legacy}
    serialized = json.dumps(cases, sort_keys=True)
    return {
        "schema": corpus.get("schema"),
        "corpus_sha256": sha256(corpus_path),
        "case_count": len(cases),
        "unique_case_ids": len(set(ids)),
        "workflow_count": len(workflows),
        "profile_count": len(profiles),
        "profile_balance": int(
            tuple(profiles) == EXPECTED_PROFILES
            and all(profiles[profile] == len(WORKFLOWS) for profile in EXPECTED_PROFILES)
        ),
        "workflow_balance": int(
            tuple(workflows) == WORKFLOWS
            and all(workflows[workflow] == len(EXPECTED_PROFILES) for workflow in WORKFLOWS)
        ),
        "case_ids_disjoint_from_normalization": int(not (set(ids) & legacy_ids)),
        "legacy_generator_tokens": int("NORM-" in serialized or "MUT-" in serialized),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "adapter-observer-heldout" / "corpus.json",
    )
    parser.add_argument(
        "--manifest",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "adapter-observer-heldout" / "MANIFEST_SHA256.txt",
    )
    parser.add_argument(
        "--output-prefix",
        type=pathlib.Path,
        default=ROOT / "analysis" / "adapter_observer_holdout",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    output_paths = [
        pathlib.Path(f"{args.output_prefix}_detail.csv"),
        pathlib.Path(f"{args.output_prefix}_summary.csv"),
        pathlib.Path(f"{args.output_prefix}_coverage.csv"),
        pathlib.Path(f"{args.output_prefix}_integrity.csv"),
    ]
    if any(path.exists() for path in output_paths) and not args.overwrite:
        raise SystemExit("audit output already exists; pass --overwrite to regenerate it")
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    checks = corpus_checks(corpus, args.corpus)
    manifest = args.manifest.read_text(encoding="ascii").strip()
    checks["manifest_matches"] = int(manifest == checks["corpus_sha256"])
    rows = audit_cases(corpus["cases"])
    checks["passed"] = sum(int(row["passed"]) for row in rows)
    checks["failures"] = sum(not int(row["passed"]) for row in rows)
    checks["normalizer_sha256"] = sha256(ROOT / "runner" / "same_tool_effects.py")
    checks["observer_sha256"] = sha256(ROOT / "runner" / "same_tool_observer.py")
    corpus_ok = (
        checks["schema"] == "psebench.adapter-observer-heldout.v1"
        and checks["case_count"] == 48
        and checks["unique_case_ids"] == 48
        and checks["workflow_count"] == len(WORKFLOWS)
        and checks["profile_count"] == len(EXPECTED_PROFILES)
        and checks["profile_balance"] == 1
        and checks["workflow_balance"] == 1
        and checks["case_ids_disjoint_from_normalization"] == 1
        and checks["legacy_generator_tokens"] == 0
        and checks["manifest_matches"] == 1
    )
    write_csv(output_paths[0], rows)
    write_csv(output_paths[1], summarize(rows, ("profile",)))
    write_csv(output_paths[2], summarize(rows, ("profile", "workflow")))
    write_csv(output_paths[3], [checks])
    if not corpus_ok or checks["failures"]:
        raise SystemExit(
            "adapter/observer held-out audit failed: "
            f"corpus_ok={int(corpus_ok)} failures={checks['failures']}"
        )
    print(
        "adapter/observer held-out audit passed: "
        f"cases={checks['case_count']} profiles={checks['profile_count']} failures=0"
    )


if __name__ == "__main__":
    main()
