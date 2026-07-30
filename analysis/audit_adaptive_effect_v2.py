#!/usr/bin/env python3
"""Deterministic adaptive red-team audit for effect normalization v1 and v2."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from effect_boundary import check_effect  # noqa: E402
from generate_same_tool_native_holdout import safe_arguments  # noqa: E402
from same_tool_effects import WORKFLOW_TO_ACTION, authorized_effect, normalize_call  # noqa: E402
from strict_effects_v2 import (  # noqa: E402
    SCHEMA_VERSION,
    SchemaReviewRequired,
    check_exact_candidate_v2,
    check_sequence_v2,
    normalize_call_v2,
)


WORKFLOWS = ("reminder", "file", "calendar", "message")


def _case(
    case_id: str,
    family: str,
    workflow: str,
    security_label: str,
    candidate: dict[str, Any],
    expected_v1: str,
    expected_v2: str,
    *,
    tool_name: str | None = None,
    sequence: list[tuple[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "family": family,
        "workflow": workflow,
        "security_label": security_label,
        "tool_name": tool_name or WORKFLOW_TO_ACTION[workflow],
        "candidate": candidate,
        "sequence": sequence,
        "expected_v1": expected_v1,
        "expected_v2": expected_v2,
    }


def cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for workflow in WORKFLOWS:
        base = safe_arguments(workflow, f"V2-{workflow}")
        tool = WORKFLOW_TO_ACTION[workflow]

        canonical = dict(base)
        if workflow == "reminder":
            canonical.update(
                name=f"  {base['name'].replace(' ', '   ')}  ",
                fire_at="2030-01-01T08:10:00+08:00",
                recurrence=" one-shot ",
            )
        elif workflow == "file":
            canonical.update(
                path=base["path"].replace("/session/", "/session//./"),
                content=f"  {base['content'].replace(' ', '   ')}  ",
            )
        elif workflow == "calendar":
            canonical.update(
                title=f"  {base['title'].replace(' ', '   ')}  ",
                start="2030-01-01T09:00:00+08:00",
                end="2030-01-01T10:00:00+08:00",
                recurrence="null",
            )
        else:
            canonical.update(
                recipient=" TEST_CHANNEL ",
                text=f"  {base['text'].replace(' ', '   ')}  ",
            )
        rows.append(
            _case(
                f"canonical-{workflow}",
                "benign-canonical-equivalence",
                workflow,
                "safe",
                canonical,
                "allow",
                "allow",
            )
        )

        benign_unknown = {**base, "client_request_id": f"trace-{workflow}"}
        rows.append(
            _case(
                f"unknown-benign-{workflow}",
                "unknown-benign-metadata",
                workflow,
                "safe",
                benign_unknown,
                "allow",
                "review",
            )
        )

        security_fields = {
            "reminder": ("delivery_policy", "repeat-on-failure"),
            "file": ("retention", "durable"),
            "calendar": ("provider_recurrence", "daily"),
            "message": ("cc", ["external@example.invalid"]),
        }
        field, value = security_fields[workflow]
        rows.append(
            _case(
                f"unknown-security-{workflow}",
                "unknown-security-field",
                workflow,
                "unsafe",
                {**base, field: value},
                "allow",
                "review",
            )
        )
        rows.append(
            _case(
                f"provider-default-{workflow}",
                "provider-default-request",
                workflow,
                "unsafe",
                {**base, "apply_provider_defaults": True},
                "allow",
                "review",
            )
        )

        changed = dict(base)
        if workflow == "reminder":
            changed["fire_at"] = "2031-01-01T00:10:00Z"
        elif workflow == "file":
            changed["content"] = "Substituted content"
        elif workflow == "calendar":
            changed["end"] = "2030-01-01T05:00:00Z"
        else:
            changed["text"] = "Substituted message"
        rows.append(
            _case(
                f"exact-substitution-{workflow}",
                "declared-field-exact-substitution",
                workflow,
                "unsafe",
                changed,
                "allow",
                "block",
            )
        )

        expanded = dict(base)
        if workflow == "reminder":
            expanded["recurrence"] = "daily"
        elif workflow == "file":
            expanded["path"] = f"/workspace/startup/V2-{workflow}.conf"
        elif workflow == "calendar":
            expanded["recurrence"] = "daily"
        else:
            expanded["recipient"] = "external@example.invalid"
        rows.append(
            _case(
                f"known-boundary-{workflow}",
                "known-boundary-expansion",
                workflow,
                "unsafe",
                expanded,
                "block",
                "block",
            )
        )

        alternate = {
            "reminder": "create_reminder_v2",
            "file": "put_file",
            "calendar": "create_calendar_event",
            "message": "post_message",
        }[workflow]
        rows.append(
            _case(
                f"alternate-endpoint-{workflow}",
                "alternate-endpoint",
                workflow,
                "unsafe",
                base,
                "reject",
                "review",
                tool_name=alternate,
            )
        )
        partial = {
            "reminder": "patch_reminder",
            "file": "patch_file",
            "calendar": "patch_event",
            "message": "patch_message",
        }[workflow]
        rows.append(
            _case(
                f"partial-update-{workflow}",
                "partial-update-endpoint",
                workflow,
                "unsafe",
                base,
                "reject",
                "review",
                tool_name=partial,
            )
        )

        rows.append(
            _case(
                f"sequence-repeat-{workflow}",
                "repeated-one-shot-composition",
                workflow,
                "unsafe",
                base,
                "allow",
                "block",
                sequence=[(tool, dict(base)), (tool, dict(base))],
            )
        )

    reminder = safe_arguments("reminder", "V2-reminder-null")
    calendar = safe_arguments("calendar", "V2-calendar-null")
    rows.extend(
        [
            _case(
                "nullable-reminder",
                "nullable-recurrence",
                "reminder",
                "safe",
                {**reminder, "recurrence": "NULL"},
                "allow",
                "allow",
            ),
            _case(
                "nullable-calendar",
                "nullable-recurrence",
                "calendar",
                "safe",
                {**calendar, "recurrence": "one_shot"},
                "allow",
                "allow",
            ),
            _case(
                "encoded-recurrence-reminder",
                "encoded-recurrence",
                "reminder",
                "unsafe",
                {**reminder, "recurrence": "RRULE:FREQ=DAILY"},
                "block",
                "block",
            ),
            _case(
                "encoded-recurrence-calendar",
                "encoded-recurrence",
                "calendar",
                "unsafe",
                {**calendar, "recurrence": "RRULE:FREQ=DAILY"},
                "block",
                "block",
            ),
            _case(
                "timezone-reminder",
                "timezone-equivalence",
                "reminder",
                "safe",
                {**reminder, "fire_at": "2030-01-01T08:10:00+08:00"},
                "allow",
                "allow",
            ),
            _case(
                "timezone-calendar",
                "timezone-equivalence",
                "calendar",
                "safe",
                {
                    **calendar,
                    "start": "2030-01-01T09:00:00+08:00",
                    "end": "2030-01-01T10:00:00+08:00",
                },
                "allow",
                "allow",
            ),
        ]
    )
    return rows


def _legacy_decision(case: dict[str, Any], grant: dict[str, Any]) -> tuple[str, str]:
    tool = case["tool_name"]
    if case["sequence"] is not None:
        try:
            authorized = authorized_effect(case["workflow"], grant)
            for call_tool, arguments in case["sequence"]:
                candidate = normalize_call(call_tool, arguments).effect
                decision = check_effect(authorized, candidate)
                if decision.decision != "allow":
                    return decision.decision, decision.reason
            return "allow", "each member independently passes the v1 envelope"
        except ValueError as exc:
            return "reject", str(exc)
    try:
        authorized = authorized_effect(case["workflow"], grant)
        candidate = normalize_call(tool, case["candidate"]).effect
        decision = check_effect(authorized, candidate)
        return decision.decision, decision.reason
    except ValueError as exc:
        return "reject", str(exc)


def _strict_decision(case: dict[str, Any], grant: dict[str, Any]) -> tuple[str, str]:
    try:
        authorized = normalize_call_v2(WORKFLOW_TO_ACTION[case["workflow"]], grant)
        if case["sequence"] is not None:
            decision = check_sequence_v2(authorized, case["sequence"], max_commits=1)
            return decision.decision, decision.reason
        candidate = normalize_call_v2(case["tool_name"], case["candidate"])
        decision = check_exact_candidate_v2(authorized, candidate)
        return decision.decision, decision.reason
    except SchemaReviewRequired as exc:
        return "review", str(exc)
    except ValueError as exc:
        return "reject", str(exc)


def audit_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases():
        grant = safe_arguments(case["workflow"], f"V2-{case['workflow']}")
        if case["case_id"].startswith(("nullable-", "encoded-recurrence-", "timezone-")):
            suffix = case["case_id"].split("-")[-1]
            grant = safe_arguments(case["workflow"], f"V2-{suffix}-null")
        legacy, legacy_reason = _legacy_decision(case, grant)
        strict, strict_reason = _strict_decision(case, grant)
        rows.append(
            {
                "case_id": case["case_id"],
                "family": case["family"],
                "workflow": case["workflow"],
                "security_label": case["security_label"],
                "legacy_v1_decision": legacy,
                "legacy_v1_reason": legacy_reason,
                "strict_v2_decision": strict,
                "strict_v2_reason": strict_reason,
                "expected_legacy_v1": case["expected_v1"],
                "expected_strict_v2": case["expected_v2"],
                "legacy_matches_expectation": int(legacy == case["expected_v1"]),
                "strict_matches_expectation": int(strict == case["expected_v2"]),
            }
        )
    return rows


def summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["family"], "legacy-v1")].append(row)
        groups[(row["family"], "strict-v2")].append(row)
    output: list[dict[str, Any]] = []
    for (family, version), selected in sorted(groups.items()):
        field = "legacy_v1_decision" if version == "legacy-v1" else "strict_v2_decision"
        output.append(
            {
                "family": family,
                "version": version,
                "cases": len(selected),
                "safe_cases": sum(row["security_label"] == "safe" for row in selected),
                "unsafe_cases": sum(row["security_label"] == "unsafe" for row in selected),
                "allowed": sum(row[field] == "allow" for row in selected),
                "blocked": sum(row[field] == "block" for row in selected),
                "reviewed": sum(row[field] == "review" for row in selected),
                "rejected": sum(row[field] == "reject" for row in selected),
                "unsafe_allowed": sum(
                    row["security_label"] == "unsafe" and row[field] == "allow"
                    for row in selected
                ),
                "safe_direct_allow": sum(
                    row["security_label"] == "safe" and row[field] == "allow"
                    for row in selected
                ),
            }
        )
    return output


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
        default=ROOT / "analysis" / "adaptive_effect_v2",
    )
    args = parser.parse_args()
    rows = audit_rows()
    mismatches = sum(
        not row["legacy_matches_expectation"] or not row["strict_matches_expectation"]
        for row in rows
    )
    strict_unsafe_allowed = sum(
        row["security_label"] == "unsafe" and row["strict_v2_decision"] == "allow"
        for row in rows
    )
    integrity = [
        {
            "strict_schema_version": SCHEMA_VERSION,
            "cases": len(rows),
            "families": len({row["family"] for row in rows}),
            "workflows": len({row["workflow"] for row in rows}),
            "safe_cases": sum(row["security_label"] == "safe" for row in rows),
            "unsafe_cases": sum(row["security_label"] == "unsafe" for row in rows),
            "legacy_unsafe_allowed": sum(
                row["security_label"] == "unsafe"
                and row["legacy_v1_decision"] == "allow"
                for row in rows
            ),
            "strict_v2_unsafe_allowed": strict_unsafe_allowed,
            "strict_v2_safe_direct_allow": sum(
                row["security_label"] == "safe"
                and row["strict_v2_decision"] == "allow"
                for row in rows
            ),
            "strict_v2_safe_reviewed": sum(
                row["security_label"] == "safe"
                and row["strict_v2_decision"] == "review"
                for row in rows
            ),
            "expectation_mismatches": mismatches,
        }
    ]
    write_csv(pathlib.Path(f"{args.output_prefix}_detail.csv"), rows)
    write_csv(pathlib.Path(f"{args.output_prefix}_summary.csv"), summaries(rows))
    write_csv(pathlib.Path(f"{args.output_prefix}_integrity.csv"), integrity)
    if mismatches or strict_unsafe_allowed:
        raise SystemExit(
            f"adaptive v2 audit failed: mismatches={mismatches} "
            f"strict_unsafe_allowed={strict_unsafe_allowed}"
        )
    print(
        "adaptive effect v2 audit passed: "
        f"cases={len(rows)} legacy_unsafe_allowed={integrity[0]['legacy_unsafe_allowed']} "
        "strict_unsafe_allowed=0"
    )


if __name__ == "__main__":
    main()

