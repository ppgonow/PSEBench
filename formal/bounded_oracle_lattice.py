#!/usr/bin/env python3
"""Exhaustive bounded audit of fixed-goal versus grant-relative labels."""

from __future__ import annotations

import json
from collections import Counter
from itertools import product


TARGETS = ("same", "other")
LIFETIMES = ("one-shot", "recurring")
SCOPES = ("same", "expanded")


def within_grant(effect: tuple[str, str, str], grant: tuple[frozenset[str], int, int]) -> bool:
    target, lifetime, scope = effect
    allowed_targets, max_lifetime, max_scope = grant
    return (
        target in allowed_targets
        and LIFETIMES.index(lifetime) <= max_lifetime
        and SCOPES.index(scope) <= max_scope
    )


def main() -> None:
    effects = list(product(TARGETS, LIFETIMES, SCOPES))
    grants = [
        (frozenset(allowed), max_lifetime, max_scope)
        for allowed in (("same",), ("other",), TARGETS)
        for max_lifetime, max_scope in product((0, 1), repeat=2)
    ]
    labels: Counter[tuple[bool, bool]] = Counter()
    for effect, grant in product(effects, grants):
        target, lifetime, _ = effect
        fixed_goal = target == "other" and lifetime == "recurring"
        grant_violation = not within_grant(effect, grant)
        labels[(fixed_goal, grant_violation)] += 1

    disagreements = labels[(True, False)] + labels[(False, True)]
    assert sum(labels.values()) == 96
    assert len([key for key, value in labels.items() if value]) == 4
    assert disagreements == 48
    print(
        json.dumps(
            {
                "effects": len(effects),
                "grants": len(grants),
                "combinations": sum(labels.values()),
                "label_cells": {
                    f"G={int(goal)},A={int(violation)}": count
                    for (goal, violation), count in sorted(labels.items())
                },
                "disagreements": disagreements,
                "interpretation": "bounded distinguishability audit, not prevalence",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
