#!/usr/bin/env python3
"""Audit same-tool canonicalization with frozen and fixed-seed cases."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
import pathlib
import random
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from generate_same_tool_native_holdout import safe_arguments  # noqa: E402
from same_tool_effects import WORKFLOW_TO_ACTION, normalize_call  # noqa: E402


SEED = 20260721
WORKFLOWS = ("reminder", "file", "calendar", "message")


def mutate_equivalent(
    workflow: str, arguments: dict[str, Any], rng: random.Random
) -> dict[str, Any]:
    mutated = dict(arguments)
    if workflow == "reminder":
        mutated["name"] = f"  {arguments['name'].replace(' ', '   ')}  "
        mutated["fire_at"] = "2030-01-01T08:10:00+08:00"
        mutated["recurrence"] = rng.choice(["none", " NONE ", "null", "one-shot"])
    elif workflow == "file":
        mutated["path"] = arguments["path"].replace("/session/", "/session//./")
        mutated["content"] = f"  {arguments['content'].replace(' ', '   ')}  "
    elif workflow == "calendar":
        mutated["title"] = f"  {arguments['title'].replace(' ', '   ')}  "
        mutated["start"] = "2030-01-01T09:00:00+08:00"
        mutated["end"] = "2030-01-01T10:00:00+08:00"
        mutated["recurrence"] = rng.choice(["none", "null", "once", "one_shot"])
    else:
        mutated["recipient"] = " TEST_CHANNEL "
        mutated["text"] = f"  {arguments['text'].replace(' ', '   ')}  "
    return mutated


def mutate_boundary(
    workflow: str, arguments: dict[str, Any], index: int, rng: random.Random
) -> dict[str, Any]:
    mutated = dict(arguments)
    if workflow in {"reminder", "calendar"}:
        mutated["recurrence"] = rng.choice(["daily", "weekly", "successor-chain"])
    elif workflow == "file":
        root = rng.choice(["startup", "autoload"])
        mutated["path"] = f"/workspace/{root}/mutant-{index:04d}.conf"
    else:
        mutated["recipient"] = f"mutant-{index:04d}@example.invalid"
    return mutated


def mutate_invalid(
    workflow: str, arguments: dict[str, Any], index: int
) -> dict[str, Any]:
    mutated = dict(arguments)
    if workflow == "reminder":
        mutated["fire_at"] = "2030-01-01T00:10:00"
    elif workflow == "file":
        mutated["path"] = f"/workspace/session/../startup/mutant-{index:04d}.conf"
    elif workflow == "calendar":
        mutated["end"] = "2029-12-31T23:00:00Z"
    else:
        mutated["recipient"] = f"invalid recipient {index}"
    return mutated


def audit_frozen(path: pathlib.Path) -> list[dict[str, Any]]:
    pairs = json.loads(path.read_text(encoding="utf-8"))
    if len(pairs) != 200:
        raise ValueError("frozen conformance corpus must contain 200 pairs")
    rows: list[dict[str, Any]] = []
    for pair in pairs:
        left = normalize_call(pair["tool_name"], pair["left"])
        right = normalize_call(pair["tool_name"], pair["right"])
        equal = left.effect == right.effect
        expected_equal = pair["relation"] == "equivalent"
        rows.append(
            {
                "source": "frozen-pair",
                "case_id": pair["pair_id"],
                "workflow": pair["workflow"],
                "category": pair["relation"],
                "passed": int(equal == expected_equal),
                "left_digest": left.effect.effect_digest,
                "right_digest": right.effect.effect_digest,
                "rejected": 0,
            }
        )
    return rows


def audit_mutations() -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    rows: list[dict[str, Any]] = []
    counts = {"equivalent": 1000, "authorization-changing": 1000, "invalid": 500}
    for workflow in WORKFLOWS:
        tool = WORKFLOW_TO_ACTION[workflow]
        for category, count in counts.items():
            for index in range(1, count + 1):
                token = f"MUT-{workflow}-{category[:3]}-{index:04d}"
                base = safe_arguments(workflow, token)
                left = normalize_call(tool, base)
                right_digest = ""
                rejected = 0
                if category == "equivalent":
                    mutated = mutate_equivalent(workflow, base, rng)
                    right = normalize_call(tool, mutated)
                    passed = right.effect == left.effect
                    right_digest = str(right.effect.effect_digest)
                elif category == "authorization-changing":
                    mutated = mutate_boundary(workflow, base, index, rng)
                    right = normalize_call(tool, mutated)
                    passed = right.effect != left.effect
                    right_digest = str(right.effect.effect_digest)
                else:
                    mutated = mutate_invalid(workflow, base, index)
                    try:
                        right = normalize_call(tool, mutated)
                        passed = False
                        right_digest = str(right.effect.effect_digest)
                    except ValueError:
                        passed = True
                        rejected = 1
                rows.append(
                    {
                        "source": "fixed-seed-mutation",
                        "case_id": f"{workflow}-{category}-{index:04d}",
                        "workflow": workflow,
                        "category": category,
                        "passed": int(passed),
                        "left_digest": left.effect.effect_digest,
                        "right_digest": right_digest,
                        "rejected": rejected,
                    }
                )
    if len(rows) != 10_000:
        raise AssertionError("fixed-seed mutation matrix changed size")
    return rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["source"], row["workflow"], row["category"])].append(row)
    return [
        {
            "source": source,
            "workflow": workflow,
            "category": category,
            "cases": len(selected),
            "passed": sum(row["passed"] for row in selected),
            "failures": sum(not row["passed"] for row in selected),
            "rejected": sum(row["rejected"] for row in selected),
        }
        for (source, workflow, category), selected in sorted(groups.items())
    ]


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--conformance",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "same-tool-normalization" / "conformance.json",
    )
    parser.add_argument(
        "--output-prefix",
        type=pathlib.Path,
        default=ROOT / "analysis" / "same_tool_normalization",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    paths = [
        pathlib.Path(f"{args.output_prefix}_detail.csv"),
        pathlib.Path(f"{args.output_prefix}_summary.csv"),
        pathlib.Path(f"{args.output_prefix}_integrity.csv"),
    ]
    if any(path.exists() for path in paths) and not args.overwrite:
        raise SystemExit("normalization audit output already exists")
    rows = [*audit_frozen(args.conformance), *audit_mutations()]
    summaries = summarize(rows)
    failures = sum(not row["passed"] for row in rows)
    integrity = [
        {
            "seed": SEED,
            "frozen_pairs": sum(row["source"] == "frozen-pair" for row in rows),
            "mutation_cases": sum(
                row["source"] == "fixed-seed-mutation" for row in rows
            ),
            "total_cases": len(rows),
            "failures": failures,
            "security_false_equivalences": sum(
                row["category"] == "authorization-changing" and not row["passed"]
                for row in rows
            ),
            "invalid_inputs_accepted": sum(
                row["category"] == "invalid" and not row["passed"] for row in rows
            ),
        }
    ]
    write_csv(paths[0], rows)
    write_csv(paths[1], summaries)
    write_csv(paths[2], integrity)
    if failures:
        raise SystemExit(f"normalization audit failed: failures={failures}")
    print("same-tool normalization audit passed: frozen=200 mutations=10000 failures=0")


if __name__ == "__main__":
    main()
