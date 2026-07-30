#!/usr/bin/env python3
"""Exact power and Wilson precision planning for confirmation framing pairs."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]


def exact_mcnemar(b: int, c: int) -> float:
    discordant = b + c
    if not discordant:
        return 1.0
    tail = sum(math.comb(discordant, i) for i in range(min(b, c) + 1))
    return min(1.0, 2 * tail / (2**discordant))


def multinomial_probability(n: int, b: int, c: int, p_plus: float, p_minus: float) -> float:
    same = n - b - c
    p_same = 1.0 - p_plus - p_minus
    coefficient = math.factorial(n) / (
        math.factorial(b) * math.factorial(c) * math.factorial(same)
    )
    return coefficient * (p_plus**b) * (p_minus**c) * (p_same**same)


def exact_power(n: int, p_plus: float, p_minus: float, alpha: float) -> float:
    if p_plus < 0 or p_minus < 0 or p_plus + p_minus > 1:
        raise ValueError("discordance probabilities must be non-negative and sum to at most one")
    power = 0.0
    for b in range(n + 1):
        for c in range(n - b + 1):
            if exact_mcnemar(b, c) <= alpha:
                power += multinomial_probability(n, b, c, p_plus, p_minus)
    return power


def wilson(k: int, n: int) -> tuple[float, float]:
    if not n:
        return 0.0, 0.0
    z = 1.96
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def minimum_consistent_discordance(n: int, alpha: float) -> Optional[int]:
    for discordant in range(1, n + 1):
        if exact_mcnemar(discordant, 0) <= alpha:
            return discordant
    return None


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", nargs="+", type=int, default=[10, 20, 30, 40, 50])
    parser.add_argument(
        "--shifts", nargs="+", type=float, default=[0.1, 0.2, 0.3, 0.4, 0.5]
    )
    parser.add_argument(
        "--power-output",
        type=Path,
        default=ROOT / "analysis" / "confirmation_power.csv",
    )
    parser.add_argument(
        "--precision-output",
        type=Path,
        default=ROOT / "analysis" / "confirmation_precision.csv",
    )
    args = parser.parse_args()
    if any(value < 1 for value in args.pairs):
        raise SystemExit("pair counts must be positive")
    if any(value <= 0 or value > 1 for value in args.shifts):
        raise SystemExit("shifts must be in (0, 1]")

    alpha_plans = (
        ("unadjusted", 0.05),
        ("three_model_primary_endpoint", 0.05 / 3),
        ("six_model_endpoint_tests", 0.05 / 6),
    )
    power_rows = []
    for n in args.pairs:
        for plan, alpha in alpha_plans:
            threshold = minimum_consistent_discordance(n, alpha)
            for shift in args.shifts:
                power_rows.append(
                    {
                        "pairs_per_endpoint_per_model": n,
                        "balanced_scenarios_per_model": 2 * n,
                        "logical_calls_three_models_two_framings": 12 * n,
                        "multiplicity_plan": plan,
                        "alpha": alpha,
                        "harmful_shift": shift,
                        "reverse_shift": 0.0,
                        "minimum_consistent_discordance": threshold,
                        "exact_power": exact_power(n, shift, 0.0, alpha),
                    }
                )
    precision_rows = []
    for n in args.pairs:
        zero = wilson(0, n)
        middle = wilson(n // 2, n)
        full = wilson(n, n)
        precision_rows.append(
            {
                "n": n,
                "zero_CI_low": zero[0],
                "zero_CI_high": zero[1],
                "half_k": n // 2,
                "half_CI_low": middle[0],
                "half_CI_high": middle[1],
                "full_CI_low": full[0],
                "full_CI_high": full[1],
            }
        )
    write_csv(args.power_output, power_rows)
    write_csv(args.precision_output, precision_rows)
    print(f"wrote {len(power_rows)} power rows and {len(precision_rows)} precision rows")


if __name__ == "__main__":
    main()
