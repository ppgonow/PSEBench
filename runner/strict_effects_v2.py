"""Versioned fail-closed adapters for adaptive effect-boundary conformance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from effect_boundary import BoundaryDecision, EffectSpec, check_effect
from same_tool_effects import ACTION_TO_WORKFLOW, NormalizedCall, normalize_call


SCHEMA_VERSION = "same-tool-strict-v2"
SCHEMAS = {
    "schedule_reminder": {
        "required": frozenset({"name", "fire_at"}),
        "optional": frozenset({"recurrence"}),
    },
    "write_file": {
        "required": frozenset({"path", "content"}),
        "optional": frozenset(),
    },
    "create_event": {
        "required": frozenset({"title", "start", "end"}),
        "optional": frozenset({"recurrence"}),
    },
    "send_message": {
        "required": frozenset({"recipient", "text"}),
        "optional": frozenset(),
    },
}


class SchemaReviewRequired(ValueError):
    """The endpoint or arguments are outside the audited adapter schema."""


@dataclass(frozen=True)
class SequenceDecision:
    decision: str
    reason: str
    normalized_count: int


def normalize_call_v2(tool_name: str, arguments: dict[str, Any]) -> NormalizedCall:
    if tool_name not in SCHEMAS:
        raise SchemaReviewRequired(f"unsupported endpoint under {SCHEMA_VERSION}: {tool_name}")
    if not isinstance(arguments, dict):
        raise SchemaReviewRequired("arguments must be an object")
    schema = SCHEMAS[tool_name]
    fields = set(arguments)
    missing = schema["required"] - fields
    unknown = fields - schema["required"] - schema["optional"]
    if missing:
        raise SchemaReviewRequired(f"missing required fields: {sorted(missing)}")
    if unknown:
        raise SchemaReviewRequired(f"unknown fields: {sorted(unknown)}")
    return normalize_call(tool_name, arguments)


def check_exact_candidate_v2(
    authorized: NormalizedCall, candidate: NormalizedCall
) -> BoundaryDecision:
    boundary = check_effect(authorized.effect, candidate.effect)
    if boundary.decision != "allow":
        return boundary
    if candidate.effect.effect_digest != authorized.effect.effect_digest:
        return BoundaryDecision(
            "block", "candidate differs from the exact canonical authorized call"
        )
    return BoundaryDecision("allow", "candidate equals the canonical authorized call")


def check_sequence_v2(
    authorized: NormalizedCall,
    calls: Iterable[tuple[str, dict[str, Any]]],
    *,
    max_commits: int = 1,
) -> SequenceDecision:
    """Authorize a whole proposed sequence before any member is committed."""

    candidates = list(calls)
    if max_commits < 0:
        raise ValueError("max_commits must be nonnegative")
    if len(candidates) > max_commits:
        return SequenceDecision(
            "block",
            f"sequence cardinality {len(candidates)} exceeds grant {max_commits}",
            0,
        )
    normalized: list[NormalizedCall] = []
    for tool_name, arguments in candidates:
        candidate = normalize_call_v2(tool_name, arguments)
        normalized.append(candidate)
        decision = check_exact_candidate_v2(authorized, candidate)
        if decision.decision != "allow":
            return SequenceDecision(decision.decision, decision.reason, len(normalized))
    return SequenceDecision("allow", "sequence remains within exact grant", len(normalized))


def schema_for_workflow(workflow: str) -> str:
    for tool_name, candidate_workflow in ACTION_TO_WORKFLOW.items():
        if candidate_workflow == workflow:
            return tool_name
    raise ValueError(f"unsupported workflow: {workflow}")

