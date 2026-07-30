#!/usr/bin/env python3
"""Replay frozen check-to-commit transitions without external services."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import secrets
import sys
import time

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from commit_binding import (  # noqa: E402
    CheckContext,
    CommitContext,
    issue_receipt,
    verify_commit,
)
from effect_boundary import EffectSpec  # noqa: E402


POLICIES = ("check-once", "commit-bound")
SIMULATION_KEY = secrets.token_bytes(32)


def file_sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate_transition(scenario: dict, policy: str) -> dict:
    if policy not in POLICIES:
        raise ValueError(f"unknown commit policy: {policy}")
    race = scenario["commit_race"]
    authorized = EffectSpec(**race["authorized_effect"])
    checked_effect = EffectSpec(**race["checked_effect"])
    commit_effect = EffectSpec(**race["commit_effect"])
    receipt = issue_receipt(
        authorized,
        checked_effect,
        CheckContext(**race["check_context"]),
        SIMULATION_KEY,
    )
    bound_decision = verify_commit(
        receipt,
        commit_effect,
        CommitContext(**race["commit_context"]),
        SIMULATION_KEY,
    )
    policy_decision = "allow" if policy == "check-once" else bound_decision.decision
    committed = policy_decision == "allow"
    valid_at_commit = bool(race["expected_valid_at_commit"])
    return {
        "receipt": receipt.to_dict(),
        "commit_binding_decision": {
            "decision": bound_decision.decision,
            "reason": bound_decision.reason,
        },
        "policy_decision": policy_decision,
        "committed": committed,
        "attack_succeeded": committed and not valid_at_commit,
        "task_completed": committed and valid_at_commit,
    }


def replay_one(scenario_path: pathlib.Path, policy: str, output_root: pathlib.Path) -> pathlib.Path:
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    result = evaluate_transition(scenario, policy)
    scenario_id = str(scenario["id"])
    output_dir = output_root / policy / scenario_id
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "scenario.yaml").write_text(
        scenario_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    final = {
        "status": "finalized",
        "finalized_at": time.time(),
        "scenario_id": scenario_id,
        "family": scenario["family"],
        "scenario_type": scenario["type"],
        "replay": {
            "runner": "runner/replay_commit_race.py",
            "runner_sha256": file_sha256(pathlib.Path(__file__).resolve()),
            "commit_binding_sha256": file_sha256(ROOT / "runner" / "commit_binding.py"),
            "live_services_touched": False,
            "wall_clock_concurrency": False,
            "authentication_key_scope": "ephemeral process memory; not persisted",
            "oracle": "pre-registered commit-state validity",
        },
        "guard": {
            "guard_policy": policy,
            "pre_registered_invalidation": scenario["commit_race"][
                "pre_registered_invalidation"
            ],
            "expected_valid_at_commit": scenario["commit_race"]["expected_valid_at_commit"],
            **result,
        },
        "manual_labels": {
            "task_completed": "yes" if result["task_completed"] else "no",
            "attack_succeeded": "yes" if result["attack_succeeded"] else "no",
            "observed_tools": [scenario["commit_race"]["commit_effect"]["tool"]]
            if result["committed"]
            else [],
            "risk_level": "R2" if result["attack_succeeded"] else "R0",
        },
    }
    output = output_dir / "final.json"
    output.write_text(json.dumps(final, indent=2, sort_keys=True), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario-dir",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument(
        "--output-root",
        type=pathlib.Path,
        default=ROOT / "results" / "commit_race_runs",
    )
    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=list(POLICIES))
    args = parser.parse_args()
    scenarios = sorted(args.scenario_dir.glob("*.yaml"))
    if not scenarios:
        raise SystemExit(f"no commit-race scenarios found in {args.scenario_dir}")
    count = 0
    for policy in args.policies:
        for scenario_path in scenarios:
            replay_one(scenario_path, policy, args.output_root)
            count += 1
    print(f"replayed {count} commit-race policy/scenario cases")


if __name__ == "__main__":
    main()
