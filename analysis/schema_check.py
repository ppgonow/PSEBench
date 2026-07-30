#!/usr/bin/env python3
"""Validate scenario YAMLs against their suite-specific schemas.

Usage:
  python3 analysis/schema_check.py
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path
from typing import Any

import yaml


LEGACY_REQUIRED = [
    "id",
    "name",
    "type",
    "injection_source",
    "injection_style",
    "target_risk",
    "target_chain",
    "prompt",
    "oracle_expectations",
]
LEGACY_RECOMMENDED = [
    "intent.user_intent",
    "intent.required_action",
    "adversary.authority",
    "adversary.source",
    "risk.class",
    "risk.escalation",
    "attack_strength",
]

SAME_TOOL_SUITE = "same-tool-native-holdout"
SAME_TOOL_REQUIRED = [
    "id",
    "template_id",
    "suite",
    "type",
    "workflow",
    "carrier",
    "exposure",
    "prompt",
    "artifact_content",
    "authorized_arguments",
    "adversary.source",
    "adversary.knowledge",
    "oracle.authorized_tool",
    "oracle.same_tool_required",
]
SAME_TOOL_WORKFLOWS = {
    "reminder": "schedule_reminder",
    "file": "write_file",
    "calendar": "create_event",
    "message": "send_message",
}
SAME_TOOL_CARRIERS = {"message", "retrieved-document", "tool-output"}
SAME_TOOL_EXPOSURES = {"clean", "injected"}


def get_nested(data: dict[str, Any], key: str) -> Any:
    current: Any = data
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def validate_same_tool(data: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    workflow = data.get("workflow")
    carrier = data.get("carrier")
    exposure = data.get("exposure")
    scenario_type = data.get("type")

    if workflow not in SAME_TOOL_WORKFLOWS:
        issues.append(f"workflow={workflow!r}")
    if carrier not in SAME_TOOL_CARRIERS:
        issues.append(f"carrier={carrier!r}")
    if exposure not in SAME_TOOL_EXPOSURES:
        issues.append(f"exposure={exposure!r}")
    expected_type = {"clean": "control", "injected": "attack"}.get(exposure)
    if expected_type is not None and scenario_type != expected_type:
        issues.append(f"type={scenario_type!r}, expected {expected_type!r}")

    scenario_id = data.get("id")
    template_id = data.get("template_id")
    if isinstance(scenario_id, str) and isinstance(template_id, str):
        if scenario_id != f"{template_id}-{exposure}":
            issues.append("id/template/exposure mismatch")

    expected_tool = SAME_TOOL_WORKFLOWS.get(workflow)
    if expected_tool is not None and get_nested(data, "oracle.authorized_tool") != expected_tool:
        issues.append("oracle.authorized_tool/workflow mismatch")
    if get_nested(data, "oracle.same_tool_required") is not True:
        issues.append("oracle.same_tool_required must be true")

    expected_source = carrier if exposure == "injected" else "none"
    if carrier in SAME_TOOL_CARRIERS and exposure in SAME_TOOL_EXPOSURES:
        if get_nested(data, "adversary.source") != expected_source:
            issues.append("adversary.source/carrier/exposure mismatch")
    if not isinstance(data.get("authorized_arguments"), dict):
        issues.append("authorized_arguments must be a mapping")
    return issues


def validate_path(path: Path) -> tuple[list[str], list[str], list[str]]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not data:
        return [], [], []
    if not isinstance(data, dict):
        return ["<mapping>"], [], ["document root must be a mapping"]

    if data.get("suite") == SAME_TOOL_SUITE:
        required = SAME_TOOL_REQUIRED
        recommended: list[str] = []
    else:
        required = LEGACY_REQUIRED
        recommended = LEGACY_RECOMMENDED

    missing_required = [key for key in required if get_nested(data, key) is None]
    missing_recommended = [
        key for key in recommended if get_nested(data, key) is None
    ]
    semantic_issues = validate_same_tool(data) if data.get("suite") == SAME_TOOL_SUITE else []
    return missing_required, missing_recommended, semantic_issues


def main() -> int:
    paths = sorted(Path(path) for path in glob.glob("scenarios/**/*.yaml", recursive=True))
    missing_required: list[tuple[Path, str]] = []
    missing_recommended: list[tuple[Path, str]] = []
    semantic_issues: list[tuple[Path, str]] = []

    for path in paths:
        required, recommended, issues = validate_path(path)
        missing_required.extend((path, key) for key in required)
        missing_recommended.extend((path, key) for key in recommended)
        semantic_issues.extend((path, issue) for issue in issues)

    print(f"checked {len(paths)} files")
    print(f"missing required: {len(missing_required)}")
    print(f"missing recommended: {len(missing_recommended)}")
    print(f"semantic issues: {len(semantic_issues)}")
    for path, key in missing_required[:50]:
        print("REQ", path, key)
    for path, issue in semantic_issues[:50]:
        print("SEM", path, issue)
    if missing_required or semantic_issues:
        return 1
    for path, key in missing_recommended[:50]:
        print("REC", path, key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
