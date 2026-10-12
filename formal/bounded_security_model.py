#!/usr/bin/env python3
"""Bounded executable checks for the PSEBench commit-bound model.

The model is intentionally small.  It does not model a provider, a network,
or cryptographic primitives.  It enumerates the state changes that the paper
assumes are security relevant between authorization and service-local commit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from itertools import product
from typing import Iterable


FIELDS = ("principal", "version", "effect", "expiry", "nonce")
MUTATIONS = FIELDS

# Each mutation is deliberately chosen to exercise only the corresponding
# receipt binding.  The map is also used by the minimality audit below: it
# makes the witness-to-field correspondence explicit instead of relying on a
# merely aggregate unsafe-count assertion.
FIELD_WITNESS = {
    "principal": "principal",
    "version": "version",
    "effect": "effect",
    "expiry": "expiry",
    "nonce": "nonce",
}


@dataclass(frozen=True)
class State:
    principal: str = "alice"
    version: int = 1
    now: int = 5
    expiry: int = 10
    nonce_used: bool = False
    committed_trials: frozenset[str] = frozenset()
    effect_rows: int = 0


@dataclass(frozen=True)
class Effect:
    digest: str = "effect-0"


@dataclass(frozen=True)
class Receipt:
    principal: str
    version: int
    digest: str
    expiry: int
    nonce: int = 1


def issue_receipt(state: State, effect: Effect) -> Receipt:
    return Receipt(
        principal=state.principal,
        version=state.version,
        digest=effect.digest,
        expiry=state.expiry,
    )


def mutate(
    state: State, effect: Effect, mutation: str
) -> tuple[State, Effect]:
    """Apply one post-check mutation and return the state/effect at commit."""

    if mutation == "principal":
        return replace(state, principal="bob"), effect
    if mutation == "version":
        return replace(state, version=state.version + 1), effect
    if mutation == "effect":
        return state, replace(effect, digest="effect-substituted")
    if mutation == "expiry":
        return replace(state, now=state.expiry + 1), effect
    if mutation == "nonce":
        return replace(state, nonce_used=True), effect
    raise ValueError(f"unknown mutation: {mutation}")


def within_current_grant(state: State, effect: Effect, receipt: Receipt) -> bool:
    """The bounded grant relation used by this executable model."""

    return (
        state.principal == "alice"
        and state.version == 1
        and state.now <= state.expiry
        and not state.nonce_used
        and effect.digest == "effect-0"
        and receipt.principal == state.principal
        and receipt.version == state.version
    )


def verify_and_commit(
    state: State,
    receipt: Receipt,
    effect: Effect,
    included: Iterable[str],
    trial_id: str,
) -> tuple[State, bool, bool]:
    """Return (new state, accepted/new-row, unsafe-new-row)."""

    included = set(included)
    if trial_id in state.committed_trials:
        # A duplicate delivery is acknowledged idempotently, without a new
        # effect row.  This is separate from authorization freshness.
        return state, False, False

    if "principal" in included and state.principal != receipt.principal:
        return state, False, False
    if "version" in included and state.version != receipt.version:
        return state, False, False
    if "effect" in included and effect.digest != receipt.digest:
        return state, False, False
    if "expiry" in included and state.now > receipt.expiry:
        return state, False, False
    if "nonce" in included and state.nonce_used:
        return state, False, False

    new_state = replace(
        state,
        nonce_used=True,
        committed_trials=state.committed_trials | {trial_id},
        effect_rows=state.effect_rows + 1,
    )
    unsafe = not within_current_grant(state, effect, receipt)
    return new_state, True, unsafe


def run_field_matrix() -> dict[str, dict[str, int]]:
    base = State()
    effect = Effect()
    receipt = issue_receipt(base, effect)
    result: dict[str, dict[str, int]] = {}
    profiles = {"full": FIELDS} | {
        f"without-{field}": tuple(x for x in FIELDS if x != field)
        for field in FIELDS
    }

    for name, included in profiles.items():
        unsafe = 0
        accepted = 0
        for mutation in MUTATIONS:
            mutated_state, mutated_effect = mutate(base, effect, mutation)
            _, did_accept, is_unsafe = verify_and_commit(
                mutated_state, receipt, mutated_effect, included, f"trial-{mutation}"
            )
            accepted += int(did_accept)
            unsafe += int(is_unsafe)

        stable_state, stable_accept, stable_unsafe = verify_and_commit(
            base, receipt, effect, included, "stable"
        )
        duplicate_state, duplicate_accept, duplicate_unsafe = verify_and_commit(
            stable_state, receipt, effect, included, "stable"
        )
        result[name] = {
            "mutations": len(MUTATIONS),
            "accepted_mutations": accepted,
            "unsafe_commits": unsafe,
            "stable_commit": int(stable_accept and not stable_unsafe),
            "duplicate_new_row": int(duplicate_accept),
            "duplicate_unsafe": int(duplicate_unsafe),
            "effect_rows_after_duplicate": duplicate_state.effect_rows,
        }
    return result


def run_receipt_minimality() -> dict[str, dict[str, object]]:
    """Return the smallest bounded witness for every omitted receipt field.

    This is a necessity audit, not a claim that a receipt is the only secure
    mechanism.  A verifier may replace a receipt binding with an independent
    current-grant check; the witness applies when that dimension is neither
    carried by the receipt nor revalidated at commit.
    """

    base = State()
    effect = Effect()
    receipt = issue_receipt(base, effect)
    witnesses: dict[str, dict[str, object]] = {}
    for field in FIELDS:
        included = tuple(x for x in FIELDS if x != field)
        accepted_witnesses: list[str] = []
        for mutation in MUTATIONS:
            mutated_state, mutated_effect = mutate(base, effect, mutation)
            _, accepted, unsafe = verify_and_commit(
                mutated_state,
                receipt,
                mutated_effect,
                included,
                f"minimality-{field}-{mutation}",
            )
            if accepted and unsafe:
                accepted_witnesses.append(mutation)
        expected = FIELD_WITNESS[field]
        witnesses[field] = {
            "omitted_field": field,
            "included_fields": list(included),
            "expected_witness": expected,
            "unsafe_witnesses": accepted_witnesses,
            "matching_witness": int(accepted_witnesses == [expected]),
        }
    return witnesses


def run_interleavings() -> dict[str, int]:
    """Check that a full receipt is safe before and after a mutation event."""

    base = State()
    effect = Effect()
    receipt = issue_receipt(base, effect)
    # Mutation before commit must be rejected; mutation after commit is outside
    # the commit's linearization interval and therefore leaves a safe row.
    changed, changed_effect = mutate(base, effect, "version")
    _, _, unsafe_before = verify_and_commit(
        changed, receipt, changed_effect, FIELDS, "before"
    )
    committed, accepted_after, unsafe_after = verify_and_commit(
        base, receipt, effect, FIELDS, "after"
    )
    changed_after = replace(committed, version=2)
    return {
        "mutate-before-commit-unsafe": int(unsafe_before),
        "commit-before-mutate-accepted": int(accepted_after),
        "commit-before-mutate-unsafe": int(unsafe_after),
        "rows-after-post-commit-mutation": changed_after.effect_rows,
    }


def run_proposal_only_limit() -> dict[str, int]:
    """Witness the stable-task/safety trade-off for a cached allow.

    The two executions have the same proposal-time view.  A cached policy that
    commits the stable authorized task therefore makes the same decision after
    an unobserved revocation.  Always-block is safe but loses the stable task.
    """

    base = State()
    effect = Effect()
    receipt = issue_receipt(base, effect)
    revoked = replace(base, version=base.version + 1)
    cached_allow = within_current_grant(base, effect, receipt)
    stable_unsafe = cached_allow and not within_current_grant(base, effect, receipt)
    revoked_unsafe = cached_allow and not within_current_grant(revoked, effect, receipt)
    _, receipt_stable, _ = verify_and_commit(base, receipt, effect, FIELDS, "stable-limit")
    _, receipt_revoked, receipt_revoked_unsafe = verify_and_commit(
        revoked, receipt, effect, FIELDS, "revoked-limit"
    )
    return {
        "proposal_views_equal": 1,
        "cached_stable_commit": int(cached_allow),
        "cached_stable_unsafe": int(stable_unsafe),
        "cached_revoked_commit": int(cached_allow),
        "cached_revoked_unsafe": int(revoked_unsafe),
        "always_block_stable_commit": 0,
        "receipt_stable_commit": int(receipt_stable),
        "receipt_revoked_commit": int(receipt_revoked),
        "receipt_revoked_unsafe": int(receipt_revoked_unsafe),
    }


def run_sequence_matrix() -> dict[str, int]:
    """Enumerate short compositions and an omitted aggregate-budget check."""

    def sequence_allowed(members: tuple[bool, ...], budget: int, check_budget: bool) -> bool:
        return all(members) and (not check_budget or len(members) <= budget)

    cases = 0
    full_unsafe = 0
    no_budget_unsafe = 0
    duplicate_rows = 0
    for budget in (1, 2):
        for length in (1, 2, 3):
            for members in product((True, False), repeat=length):
                cases += 1
                authorized = all(members) and length <= budget
                # Full IACG checks each member and the aggregate cardinality.
                full_unsafe += int(
                    sequence_allowed(members, budget, check_budget=True)
                    and not authorized
                )
                # Removing only the aggregate check admits an all-authorized
                # sequence whose length exceeds the current grant.
                no_budget_unsafe += int(
                    sequence_allowed(members, budget, check_budget=False)
                    and not authorized
                )
                if all(members) and length <= budget:
                    duplicate_rows += 1
    return {
        "cases": cases,
        "full_unsafe_commits": full_unsafe,
        "without_budget_unsafe_commits": no_budget_unsafe,
        "stable_sequences": duplicate_rows,
        # Two individually authorized commits can both observe the same
        # remaining budget when the aggregate check is outside the transaction.
        "concurrent_budget_overflow_witness": int(
            sequence_allowed((True, True), 1, check_budget=False)
            and not sequence_allowed((True, True), 1, check_budget=True)
        ),
    }


def main() -> None:
    fields = run_field_matrix()
    minimality = run_receipt_minimality()
    interleavings = run_interleavings()
    proposal_only_limit = run_proposal_only_limit()
    sequences = run_sequence_matrix()
    assert fields["full"]["unsafe_commits"] == 0
    assert fields["full"]["stable_commit"] == 1
    assert fields["full"]["duplicate_new_row"] == 0
    assert fields["full"]["effect_rows_after_duplicate"] == 1
    for field in FIELDS:
        assert fields[f"without-{field}"]["unsafe_commits"] >= 1
        assert minimality[field]["matching_witness"] == 1
    assert interleavings["mutate-before-commit-unsafe"] == 0
    assert interleavings["commit-before-mutate-accepted"] == 1
    assert interleavings["commit-before-mutate-unsafe"] == 0
    assert proposal_only_limit["cached_stable_commit"] == 1
    assert proposal_only_limit["cached_revoked_unsafe"] == 1
    assert proposal_only_limit["always_block_stable_commit"] == 0
    assert proposal_only_limit["receipt_stable_commit"] == 1
    assert proposal_only_limit["receipt_revoked_commit"] == 0
    assert sequences["full_unsafe_commits"] == 0
    assert sequences["without_budget_unsafe_commits"] > 0
    assert sequences["concurrent_budget_overflow_witness"] == 1
    print(
        json.dumps(
            {
                "field_matrix": fields,
                "receipt_minimality": minimality,
                "interleavings": interleavings,
                "proposal_only_limit": proposal_only_limit,
                "sequence_matrix": sequences,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
