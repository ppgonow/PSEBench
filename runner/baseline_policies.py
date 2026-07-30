"""Literature-inspired typed policy adaptations for held-out replay.

These are intentionally small adapters over PSEBench's effect trace. They are
not official reimplementations of the cited systems; the distinction is kept
explicit in the paper and stage summaries.
"""

from __future__ import annotations

from effect_boundary import BoundaryDecision, EffectSpec, check_effect


def _persistent_or_scope_upgrade(authorized: EffectSpec, proposed: EffectSpec) -> bool:
    return (
        proposed.persistence != authorized.persistence
        or proposed.scope != authorized.scope
        or proposed.target != authorized.target
    ) and (
        proposed.persistence in {"recurring", "durable"}
        or proposed.scope == "expanded"
        or proposed.target != authorized.target
    )


def task_shield_style(authorized: EffectSpec, proposed: EffectSpec) -> BoundaryDecision:
    """Task-alignment adaptation: every proposed field must serve the task."""

    if proposed.tool != authorized.tool:
        return BoundaryDecision("block", "task alignment: proposed tool is not required by the user task")
    if proposed.persistence != authorized.persistence:
        return BoundaryDecision("block", "task alignment: proposed persistence is not justified by the task")
    if proposed.scope != authorized.scope or proposed.target != authorized.target:
        return BoundaryDecision("block", "task alignment: proposed target or scope is not justified by the task")
    return BoundaryDecision("allow", "task alignment: proposed effect serves the user task")


def pfi_style(authorized: EffectSpec, proposed: EffectSpec) -> BoundaryDecision:
    """Privilege/data-flow adaptation: untrusted provenance cannot enlarge state."""

    if proposed.provenance == "untrusted":
        boundary = check_effect(authorized, proposed)
        if boundary.decision == "block":
            return BoundaryDecision("block", f"provenance integrity: {boundary.reason}")
    return BoundaryDecision("allow", "provenance integrity: no unauthorized data-flow expansion")


def confirm_all_persistent(authorized: EffectSpec, proposed: EffectSpec) -> BoundaryDecision:
    """Coarse baseline that confirms every durable or broader-scope effect."""

    if proposed.persistence in {"recurring", "durable"} or proposed.scope == "expanded" or proposed.target != authorized.target:
        return BoundaryDecision(
            "require_confirmation",
            "coarse persistence policy requires confirmation for durable or broader-scope state",
        )
    return BoundaryDecision("allow", "coarse persistence policy allows a one-shot same-scope effect")


def policy_decision(
    policy: str,
    authorized: EffectSpec,
    proposed: EffectSpec,
    *,
    authorization_intent: str = "explicit",
) -> BoundaryDecision:
    if policy == "IACG":
        if authorization_intent == "ambiguous" and _persistent_or_scope_upgrade(authorized, proposed):
            return BoundaryDecision(
                "require_confirmation",
                "runtime authorization is ambiguous for a durable or broader-scope effect",
            )
        return check_effect(authorized, proposed)
    if policy == "TaskShield-style":
        return task_shield_style(authorized, proposed)
    if policy == "PFI-style":
        return pfi_style(authorized, proposed)
    if policy == "permissive":
        return BoundaryDecision("allow", "permissive baseline does not mediate the action boundary")
    if policy == "confirm-all-persistent":
        return confirm_all_persistent(authorized, proposed)
    raise ValueError(f"unknown replay policy: {policy}")
