#!/usr/bin/env python3
"""Bounded multi-principal authorization and delegation audit.

This dependency-free model exercises the grant dimensions that are not covered
by the single-principal receipt matrix: delegated principals, partial target /
lifetime / scope grants, aggregate budgets, revocation, and an owner switch.
It is a conformance audit of the stated relation, not a model attack-rate
estimate and not a provider implementation.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable


LIFETIMES = ("one-shot", "recurring")
SCOPES = ("same", "expanded")
PROFILES = (
    "owner-stable",
    "delegated-stable",
    "partial-target",
    "partial-lifetime",
    "partial-scope",
    "delegation-revoked",
    "owner-conflict",
    "budget-shrink",
    "outsider",
)


@dataclass(frozen=True)
class Grant:
    owner: str
    principal: str
    version: int
    active: bool
    targets: frozenset[str]
    max_lifetime: int
    max_scope: int
    max_commits: int


@dataclass(frozen=True)
class Effect:
    principal: str
    target: str
    lifetime: str
    scope: str
    count: int = 1


@dataclass(frozen=True)
class Receipt:
    owner: str
    principal: str
    version: int
    effect: Effect
    max_commits: int


TARGETS = (
    "calendar:team",
    "calendar:private",
    "file:/workspace/session/note",
    "message:test_channel",
)


def relation(grant: Grant, effect: Effect) -> bool:
    return (
        grant.active
        and effect.principal == grant.principal
        and effect.target in grant.targets
        and LIFETIMES.index(effect.lifetime) <= grant.max_lifetime
        and SCOPES.index(effect.scope) <= grant.max_scope
        and effect.count <= grant.max_commits
    )


def issue(grant: Grant, effect: Effect) -> Receipt:
    if not relation(grant, effect):
        raise ValueError("cannot issue a receipt for an unauthorized proposal")
    return Receipt(grant.owner, grant.principal, grant.version, effect, grant.max_commits)


def receipt_bound_commit(grant: Grant, receipt: Receipt, effect: Effect) -> str:
    """Return allow/block while checking all current grant bindings."""

    if receipt.owner != grant.owner or receipt.principal != grant.principal:
        return "block-principal"
    if receipt.version != grant.version:
        return "block-version"
    if receipt.max_commits != grant.max_commits:
        return "block-budget"
    if receipt.effect != effect:
        return "block-effect"
    return "allow" if relation(grant, effect) else "block-relation"


def cached_proposal_commit(proposal: Grant, current: Grant, receipt: Receipt, effect: Effect) -> str:
    """Model a proposal-time allow that never rechecks current authority."""

    if not relation(proposal, effect):
        return "block-proposal"
    return "allow-stale" if current != proposal else "allow"


def _base(principal: str = "alice", *, owner: str = "alice", version: int = 7) -> Grant:
    return Grant(
        owner=owner,
        principal=principal,
        version=version,
        active=True,
        targets=frozenset(TARGETS),
        max_lifetime=1,
        max_scope=1,
        max_commits=2,
    )


def cases() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for profile in PROFILES:
        for index, target in enumerate(TARGETS, 1):
            proposal = _base("alice")
            effect = Effect("alice", target, "one-shot", "same")
            current = proposal
            expected_full = "allow"
            expected_cached = "allow"
            if profile == "delegated-stable":
                proposal = _base("bob")
                effect = replace(effect, principal="bob")
                current = proposal
            elif profile == "partial-target":
                expected_full = "block"
                expected_cached = "allow-stale"
                current = replace(
                    proposal,
                    targets=frozenset(set(TARGETS) - {target}),
                )
            elif profile == "partial-lifetime":
                proposal = replace(proposal, max_lifetime=1)
                effect = replace(effect, lifetime="recurring")
                expected_full = "block"
                expected_cached = "allow-stale"
                current = replace(proposal, max_lifetime=0)
            elif profile == "partial-scope":
                proposal = replace(proposal, max_scope=1)
                effect = replace(effect, scope="expanded")
                expected_full = "block"
                expected_cached = "allow-stale"
                current = replace(proposal, max_scope=0)
            elif profile == "delegation-revoked":
                proposal = _base("bob")
                effect = replace(effect, principal="bob")
                expected_full = "block"
                expected_cached = "allow-stale"
                current = replace(proposal, version=8, active=False)
            elif profile == "owner-conflict":
                expected_full = "block"
                expected_cached = "allow-stale"
                current = replace(proposal, owner="bob", principal="bob")
            elif profile == "budget-shrink":
                proposal = replace(proposal, max_commits=2)
                effect = replace(effect, count=2)
                expected_full = "block"
                expected_cached = "allow-stale"
                current = replace(proposal, max_commits=1)
            elif profile == "outsider":
                effect = replace(effect, principal="carol")
                expected_full = "no-receipt"
                expected_cached = "no-receipt"

            try:
                receipt = issue(proposal, effect)
            except ValueError:
                receipt = None
            full = "no-receipt" if receipt is None else receipt_bound_commit(current, receipt, effect)
            cached = (
                "no-receipt"
                if receipt is None
                else cached_proposal_commit(proposal, current, receipt, effect)
            )
            unsafe_cached = cached == "allow-stale" and not relation(current, effect)
            rows.append(
                {
                    "case_id": f"MP-{profile}-{index:02d}",
                    "profile": profile,
                    "target": target,
                    "proposal_principal": proposal.principal,
                    "current_principal": current.principal,
                    "proposal_owner": proposal.owner,
                    "current_owner": current.owner,
                    "proposal_version": proposal.version,
                    "current_version": current.version,
                    "proposal_targets": "|".join(sorted(proposal.targets)),
                    "current_targets": "|".join(sorted(current.targets)),
                    "effect_lifetime": effect.lifetime,
                    "effect_scope": effect.scope,
                    "effect_count": effect.count,
                    "proposal_max_commits": proposal.max_commits,
                    "current_max_commits": current.max_commits,
                    "receipt_bound": full,
                    "cached_proposal": cached,
                    "current_relation": int(relation(current, effect)),
                    "unsafe_cached": int(unsafe_cached),
                    "expected_full": expected_full,
                    "expected_cached": expected_cached,
                }
            )
    return rows


def audit(rows: Iterable[dict[str, object]]) -> dict[str, object]:
    selected = list(rows)
    stale = [row for row in selected if row["profile"] in {
        "partial-target", "partial-lifetime", "partial-scope",
        "delegation-revoked", "owner-conflict", "budget-shrink",
    }]
    stable = [row for row in selected if row["profile"] in {"owner-stable", "delegated-stable"}]
    outsider = [row for row in selected if row["profile"] == "outsider"]
    return {
        "cases": len(selected),
        "profiles": len({row["profile"] for row in selected}),
        "stable_controls": len(stable),
        "stale_authority_cases": len(stale),
        "outsider_cases": len(outsider),
        "receipt_bound_all_expected": int(
            all(
                (str(row["receipt_bound"]).startswith("block") if row["expected_full"] == "block" else row["receipt_bound"] == row["expected_full"])
                for row in selected
            )
        ),
        "cached_all_expected": int(all(row["cached_proposal"] == row["expected_cached"] for row in selected)),
        "receipt_bound_safe_commits": sum(row["receipt_bound"] == "allow" for row in selected),
        "receipt_bound_blocks": sum(str(row["receipt_bound"]).startswith("block") for row in selected),
        "receipt_bound_block_reasons": {
            reason: sum(row["receipt_bound"] == reason for row in selected)
            for reason in sorted({str(row["receipt_bound"]) for row in selected if str(row["receipt_bound"]).startswith("block")})
        },
        "cached_stale_unsafe_commits": sum(int(row["unsafe_cached"]) for row in selected),
        "cached_stale_cases": sum(row["cached_proposal"] == "allow-stale" for row in selected),
        "mutation_families": {
            profile: sum(row["profile"] == profile for row in selected)
            for profile in PROFILES
        },
        "interpretation": "bounded multi-principal conformance audit, not a prevalence estimate",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = cases()
    summary = audit(rows)
    assert summary["cases"] == 36
    assert summary["profiles"] == 9
    assert summary["stable_controls"] == 8
    assert summary["stale_authority_cases"] == 24
    assert summary["outsider_cases"] == 4
    assert summary["receipt_bound_all_expected"] == 1
    assert summary["cached_all_expected"] == 1
    assert summary["receipt_bound_safe_commits"] == 8
    assert summary["cached_stale_unsafe_commits"] == 24
    output = {"summary": summary, "rows": rows}
    serialized = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")


if __name__ == "__main__":
    main()
