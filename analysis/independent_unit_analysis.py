#!/usr/bin/env python3
"""Separate descriptive run inventory from independent paired scenario results."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
FROZEN_OUTCOMES = ROOT / "analysis" / "independent_paired_outcomes.csv"


@dataclass(frozen=True)
class Outcome:
    scenario_id: str
    attack: bool
    task: bool


@dataclass(frozen=True)
class PairSpec:
    name: str
    execution_surface: str
    baseline_runs: tuple[str, ...]
    iacg_runs: tuple[str, ...]


PAIR_SPECS = (
    PairSpec(
        "Core cron",
        "scripted tool-policy harness",
        ("g1fixed-permissive",),
        ("g2-permissive-guard",),
    ),
    PairSpec(
        "Adaptive cron",
        "scripted tool-policy harness",
        ("adaptive1-adaptive-permissive", "adaptive2-adaptive-permissive"),
        ("adaptive1-adaptive-guard", "adaptive2-adaptive-guard"),
    ),
    PairSpec(
        "Live replica",
        "OpenClaw model plus cron tool",
        ("live5-live5-permissive",),
        ("live5-live5-guard",),
    ),
    PairSpec(
        "File persistence",
        "local sandbox artifact harness",
        ("riskfix2-noncron-file-permissive",),
        ("riskfix2-noncron-file-iacg",),
    ),
    PairSpec(
        "Calendar recurrence",
        "local sandbox artifact harness",
        ("riskfix2-noncron-calendar-permissive",),
        ("riskfix2-noncron-calendar-iacg",),
    ),
    PairSpec(
        "Recipient hijack",
        "local simulated-recipient harness",
        ("riskfix2-noncron-recipient-permissive",),
        ("riskfix2-noncron-recipient-iacg",),
    ),
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        raise ValueError("Wilson interval requires n > 0")
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def ci_text(k: int, n: int) -> str:
    low, high = wilson(k, n)
    return f"[{low:.3f},{high:.3f}]"


def exact_mcnemar(b: int, c: int) -> float:
    discordant = b + c
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, value) for value in range(0, min(b, c) + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def load_condition(run_root: Path, run_names: Iterable[str]) -> dict[str, Outcome]:
    outcomes: dict[str, Outcome] = {}
    for run_name in run_names:
        run_dir = run_root / run_name
        if not run_dir.is_dir():
            raise ValueError(f"missing run directory: {run_dir}")
        for final_path in sorted(run_dir.glob("*/final.json")):
            scenario_id = final_path.parent.name
            if scenario_id in outcomes:
                raise ValueError(f"duplicate scenario {scenario_id} across condition roots")
            final = json.loads(final_path.read_text(encoding="utf-8"))
            labels = final.get("manual_labels") or {}
            attack = labels.get("attack_succeeded")
            task = labels.get("task_completed")
            if attack not in {"yes", "no"} or task not in {"yes", "no"}:
                raise ValueError(f"invalid labels in {final_path}: attack={attack!r}, task={task!r}")
            outcomes[scenario_id] = Outcome(scenario_id, attack == "yes", task == "yes")
    if not outcomes:
        raise ValueError(f"no finalized outcomes for runs: {list(run_names)}")
    return outcomes


def expected_run_names() -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            run_name
            for spec in PAIR_SPECS
            for run_name in (*spec.baseline_runs, *spec.iacg_runs)
        )
    )


def extract_outcome_rows(run_root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for spec in PAIR_SPECS:
        for condition, run_names in (
            ("baseline", spec.baseline_runs),
            ("iacg", spec.iacg_runs),
        ):
            outcomes = load_condition(run_root, run_names)
            for scenario_id, outcome in sorted(outcomes.items()):
                rows.append(
                    {
                        "slice": spec.name,
                        "execution_surface": spec.execution_surface,
                        "condition": condition,
                        "scenario_id": scenario_id,
                        "attack_succeeded": "yes" if outcome.attack else "no",
                        "task_completed": "yes" if outcome.task else "no",
                    }
                )
    return rows


def pairs_from_outcome_rows(
    rows: list[dict[str, str]],
) -> dict[str, tuple[dict[str, Outcome], dict[str, Outcome]]]:
    specs = {spec.name: spec for spec in PAIR_SPECS}
    pairs = {spec.name: ({}, {}) for spec in PAIR_SPECS}
    if not rows:
        raise ValueError("frozen independent outcome table is empty")
    for row in rows:
        slice_name = row.get("slice", "")
        if slice_name not in specs:
            raise ValueError(f"unexpected independent outcome slice: {slice_name!r}")
        spec = specs[slice_name]
        if row.get("execution_surface") != spec.execution_surface:
            raise ValueError(f"execution surface mismatch for {slice_name}")
        condition = row.get("condition")
        if condition not in {"baseline", "iacg"}:
            raise ValueError(f"invalid condition for {slice_name}: {condition!r}")
        scenario_id = row.get("scenario_id", "")
        attack = row.get("attack_succeeded")
        task = row.get("task_completed")
        if not scenario_id or attack not in {"yes", "no"} or task not in {"yes", "no"}:
            raise ValueError(f"invalid frozen outcome row for {slice_name}: {row}")
        target = pairs[slice_name][0 if condition == "baseline" else 1]
        if scenario_id in target:
            raise ValueError(f"duplicate frozen outcome: {slice_name}/{condition}/{scenario_id}")
        target[scenario_id] = Outcome(scenario_id, attack == "yes", task == "yes")
    for spec in PAIR_SPECS:
        baseline, iacg = pairs[spec.name]
        if not baseline or not iacg:
            raise ValueError(f"missing condition rows for {spec.name}")
    return pairs


def load_paired_outcomes(
    run_root: Path, frozen_path: Path
) -> tuple[dict[str, tuple[dict[str, Outcome], dict[str, Outcome]]], str]:
    presence = {name: (run_root / name).is_dir() for name in expected_run_names()}
    if all(presence.values()):
        rows = extract_outcome_rows(run_root)
        write_csv(frozen_path, rows)
        return pairs_from_outcome_rows(
            [{key: str(value) for key, value in row.items()} for row in rows]
        ), "raw_final_json"
    if any(presence.values()):
        missing = sorted(name for name, exists in presence.items() if not exists)
        raise ValueError(f"partial independent raw-run inventory; missing={missing}")
    if not frozen_path.is_file():
        raise ValueError(f"missing frozen independent outcome table: {frozen_path}")
    return pairs_from_outcome_rows(read_csv(frozen_path)), "frozen_outcome_table"


def summarize_pair(name: str, surface: str, baseline: dict[str, Outcome], iacg: dict[str, Outcome]) -> dict[str, object]:
    baseline_ids = set(baseline)
    iacg_ids = set(iacg)
    if baseline_ids != iacg_ids:
        raise ValueError(
            f"{name} scenario mismatch: baseline_only={sorted(baseline_ids - iacg_ids)}, "
            f"iacg_only={sorted(iacg_ids - baseline_ids)}"
        )
    ids = sorted(baseline_ids)
    baseline_attack = sum(baseline[item].attack for item in ids)
    iacg_attack = sum(iacg[item].attack for item in ids)
    baseline_task = sum(baseline[item].task for item in ids)
    iacg_task = sum(iacg[item].task for item in ids)
    b = sum(baseline[item].attack and not iacg[item].attack for item in ids)
    c = sum(not baseline[item].attack and iacg[item].attack for item in ids)
    return {
        "slice": name,
        "execution_surface": surface,
        "n_unique_scenarios": len(ids),
        "baseline_attack_yes": baseline_attack,
        "iacg_attack_yes": iacg_attack,
        "baseline_task_yes": baseline_task,
        "iacg_task_yes": iacg_task,
        "baseline_attack_wilson95": ci_text(baseline_attack, len(ids)),
        "iacg_attack_wilson95": ci_text(iacg_attack, len(ids)),
        "baseline_yes_iacg_no": b,
        "baseline_no_iacg_yes": c,
        "mcnemar_exact_p": f"{exact_mcnemar(b, c):.12g}",
    }


def inventory_rows(manifest_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    scopes = (
        ("Original inventory", lambda row: True),
        ("Tool induction", lambda row: row["family"].startswith("A-")),
        ("Hybrid legitimate tool", lambda row: row["family"].startswith("H-")),
        ("Cron required", lambda row: row["family"] == "H-msg-cron-required"),
        ("H-web negative", lambda row: row["family"] == "H-web-msg-required"),
    )
    output: list[dict[str, object]] = []
    for scope, predicate in scopes:
        rows = [row for row in manifest_rows if predicate(row)]
        output.append(
            {
                "scope": scope,
                "run_observations": len(rows),
                "unique_scenarios": len({row["scenario_id"] for row in rows}),
                "unique_run_ids": len({row["run_id"] for row in rows}),
                "attack_yes_observations": sum(row["attack_succeeded"] == "yes" for row in rows),
                "statistical_use": "descriptive_inventory_only",
            }
        )
    return output


def main() -> None:
    manifest = read_csv(ROOT / "analysis" / "run_manifest.csv")
    inventory = inventory_rows(manifest)
    run_root = ROOT / "results" / "runs"
    paired_outcomes, outcome_source = load_paired_outcomes(run_root, FROZEN_OUTCOMES)
    paired = []
    for spec in PAIR_SPECS:
        baseline, iacg = paired_outcomes[spec.name]
        paired.append(summarize_pair(spec.name, spec.execution_surface, baseline, iacg))
    write_csv(ROOT / "analysis" / "independent_unit_inventory.csv", inventory)
    write_csv(ROOT / "analysis" / "independent_paired_primary.csv", paired)
    print(
        f"inventory_scopes={len(inventory)} paired_slices={len(paired)} "
        f"paired_unique_scenarios={sum(int(row['n_unique_scenarios']) for row in paired)} "
        f"outcome_source={outcome_source}"
    )


if __name__ == "__main__":
    main()
