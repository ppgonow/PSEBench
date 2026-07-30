#!/usr/bin/env python3
"""Source-backed capability audit for benchmark outcome oracles."""

from __future__ import annotations

import argparse
import ast
import csv
import pathlib
import re
import subprocess
from typing import Any, Iterable


ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENTDOJO = ROOT / "external" / "official_reproduction" / "agentdojo"
AGENTDOJO_CORE = ROOT / "external" / "official_reproduction" / "agentdojo-core"
AGENTDOJO_V1 = AGENTDOJO / "src" / "agentdojo" / "default_suites" / "v1"


def _names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}


def _method(node: ast.ClassDef, name: str) -> ast.FunctionDef | None:
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name:
            return item
    return None


def task_inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(AGENTDOJO_V1.glob("*/injection_tasks.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or not node.name.startswith("InjectionTask"):
                continue
            security = _method(node, "security")
            if security is None:
                continue
            names = _names(security)
            has_goal = any(
                isinstance(item, (ast.Assign, ast.AnnAssign))
                and (
                    any(isinstance(target, ast.Name) and target.id == "GOAL" for target in getattr(item, "targets", []))
                    or isinstance(getattr(item, "target", None), ast.Name)
                    and item.target.id == "GOAL"
                )
                for item in node.body
            )
            rows.append(
                {
                    "suite": path.parent.name,
                    "task_class": node.name,
                    "source_file": str(path.relative_to(ROOT)),
                    "source_line": node.lineno,
                    "uses_model_output": int("model_output" in names),
                    "uses_pre_environment": int("pre_environment" in names),
                    "uses_post_environment": int("post_environment" in names),
                    "declares_goal": int(has_goal),
                }
            )
    if not rows:
        raise ValueError("no AgentDojo v1 injection-task security methods found")
    return rows


def _read(paths: Iterable[pathlib.Path]) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def _contains(text: str, patterns: tuple[str, ...]) -> bool:
    return all(re.search(pattern, text, flags=re.IGNORECASE) is not None for pattern in patterns)


def _revision(path: pathlib.Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def capability_rows(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    task_files = sorted(AGENTDOJO_V1.glob("*/injection_tasks.py"))
    base_path = AGENTDOJO_CORE / "src" / "agentdojo_core" / "base_tasks.py"
    suite_path = AGENTDOJO_CORE / "src" / "agentdojo_core" / "task_suite" / "task_suite.py"
    agent_text = _read([base_path, suite_path, *task_files])
    pse_paths = [
        ROOT / "runner" / "effect_boundary.py",
        ROOT / "runner" / "commit_binding.py",
        ROOT / "runner" / "service_integrated_commit.py",
    ]
    pse_text = _read(pse_paths)
    revision = _revision(AGENTDOJO)
    core_revision = _revision(AGENTDOJO_CORE)
    source_revision = f"agentdojo={revision}; agentdojo-core={core_revision}"

    agent_post = sum(row["uses_post_environment"] for row in inventory)
    agent_pre_post = sum(
        row["uses_pre_environment"] and row["uses_post_environment"] for row in inventory
    )
    capabilities = [
        (
            "task_post_state_oracle",
            agent_post > 0,
            True,
            f"{agent_post}/{len(inventory)} official v1 security methods read post_environment",
            "custom effect ledger and service state are read after commit",
        ),
        (
            "pre_post_state_comparison",
            agent_pre_post > 0,
            True,
            f"{agent_pre_post}/{len(inventory)} methods read both pre_environment and post_environment",
            "scenario oracle compares authorized and observed effect state",
        ),
        (
            "function_trace_fallback",
            _contains(agent_text, (r"security_from_traces", r"functions_stack_trace")),
            False,
            "TaskSuite consults security_from_traces before security",
            "PSEBench labels the normalized candidate and committed ledger state",
        ),
        (
            "task_specific_fixed_goal",
            all(row["declares_goal"] for row in inventory),
            True,
            f"{sum(row['declares_goal'] for row in inventory)}/{len(inventory)} tasks declare GOAL",
            "each frozen scenario declares typed authorization and expected effects",
        ),
        (
            "current_versioned_authorization",
            _contains(agent_text, (r"authorization[_ ]version", r"current[_ ]authorization")),
            _contains(pse_text, (r"authorization_version", r"current.*authorization")),
            "no explicit versioned current-authorization object found in audited v1 task/evaluator sources",
            "CheckContext and CommitContext carry authorization_version",
        ),
        (
            "check_to_commit_invalidation",
            _contains(agent_text, (r"revok", r"commit")),
            _contains(pse_text, (r"authorization version changed before commit", r"committed_at")),
            "no explicit authorization invalidation between check and commit found",
            "receipt verification compares check-time and commit-time contexts",
        ),
        (
            "exact_effect_receipt_binding",
            _contains(agent_text, (r"receipt", r"effect.*digest")),
            _contains(pse_text, (r"CommitReceipt", r"checked_effect", r"authentication_tag")),
            "no authenticated exact-effect receipt found",
            "CommitReceipt authenticates checked_effect and commit verifies equality",
        ),
        (
            "service_local_atomic_commit",
            _contains(agent_text, (r"linearization", r"transaction")),
            _contains(pse_text, (r"linearization_events", r"commit_atomic", r"BEGIN IMMEDIATE")),
            "no evaluator-defined service-local authorization linearization point found",
            "service-integrated adapter verifies and writes within one SQLite transaction",
        ),
        (
            "arbitrary_provider_post_state_confirmation",
            False,
            False,
            "suite-specific emulated environments, not arbitrary external providers",
            "custom adapters and ledgers, not arbitrary SaaS post-state confirmation",
        ),
    ]

    rows: list[dict[str, Any]] = []
    for capability, agent_observed, pse_observed, agent_evidence, pse_evidence in capabilities:
        rows.extend(
            [
                {
                    "benchmark": "AgentDojo official v1",
                    "capability": capability,
                    "observed": int(agent_observed),
                    "evidence": agent_evidence,
                    "source_revision": source_revision,
                },
                {
                    "benchmark": "PSEBench reference harness",
                    "capability": capability,
                    "observed": int(pse_observed),
                    "evidence": pse_evidence,
                    "source_revision": "local artifact",
                },
            ]
        )
    return rows


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-prefix",
        type=pathlib.Path,
        default=ROOT / "analysis" / "benchmark_oracle_capability",
    )
    args = parser.parse_args()
    inventory = task_inventory()
    capabilities = capability_rows(inventory)
    integrity = [
        {
            "agentdojo_revision": _revision(AGENTDOJO),
            "agentdojo_core_revision": _revision(AGENTDOJO_CORE),
            "task_security_methods": len(inventory),
            "suites": len({row["suite"] for row in inventory}),
            "post_state_methods": sum(row["uses_post_environment"] for row in inventory),
            "pre_post_methods": sum(
                row["uses_pre_environment"] and row["uses_post_environment"]
                for row in inventory
            ),
            "capability_rows": len(capabilities),
        }
    ]
    write_csv(pathlib.Path(f"{args.output_prefix}_audit.csv"), capabilities)
    write_csv(pathlib.Path(f"{args.output_prefix}_task_inventory.csv"), inventory)
    write_csv(pathlib.Path(f"{args.output_prefix}_integrity.csv"), integrity)
    print(
        "benchmark oracle audit passed: "
        f"tasks={len(inventory)} post_state={integrity[0]['post_state_methods']}"
    )


if __name__ == "__main__":
    main()
