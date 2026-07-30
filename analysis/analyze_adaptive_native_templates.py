#!/usr/bin/env python3
"""Recompute adaptive native outcomes at the semantic-template level."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


POLICIES = ("permissive", "IACG")
BOUNDARIES = ("cron", "file", "calendar", "recipient")


def exact_mcnemar(left_only: int, right_only: int) -> float:
    discordant = left_only + right_only
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, index) for index in range(min(left_only, right_only) + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((rate * (1 - rate) + z * z / (4 * total)) / total) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def read_manifest(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    result = {row["scenario_id"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError("manifest contains duplicate scenario IDs")
    return result


def read_jsonl(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = (str(row["requested_alias"]), str(row["scenario_id"]))
            if key in seen:
                raise ValueError(f"duplicate alias/scenario unit: {key}")
            seen.add(key)
            rows.append(row)
    return rows


def template_rows(
    rows: list[dict[str, Any]], manifest: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        scenario_id = str(row["scenario_id"])
        if scenario_id not in manifest:
            raise ValueError(f"scenario missing from manifest: {scenario_id}")
        item = manifest[scenario_id]
        boundary = str(row["boundary"])
        if boundary != item["boundary"]:
            raise ValueError(f"boundary mismatch for {scenario_id}")
        groups[(str(row["requested_alias"]), boundary, int(item["template_index"]))].append(row)

    output: list[dict[str, Any]] = []
    for (alias, boundary, template_index), items in sorted(groups.items()):
        valid = [item for item in items if len(item.get("branches") or {}) == 2]
        record: dict[str, Any] = {
            "requested_alias": alias,
            "boundary": boundary,
            "template_index": template_index,
            "instances": len(items),
            "valid_instances": len(valid),
        }
        for policy in POLICIES:
            attacks = sum(bool(item["branches"][policy]["attack_succeeded"]) for item in valid)
            tasks = sum(bool(item["branches"][policy]["primary_effect_completed"]) for item in valid)
            record[f"{policy}_attack_instances"] = attacks
            record[f"{policy}_attack_any"] = int(attacks > 0)
            record[f"{policy}_task_instances"] = tasks
            record[f"{policy}_task_all"] = int(bool(valid) and tasks == len(valid))
        output.append(record)
    return output


def summary_rows(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aliases = sorted({str(row["requested_alias"]) for row in details})
    output: list[dict[str, Any]] = []
    for alias in aliases:
        for boundary in (*BOUNDARIES, "overall"):
            selected = [
                row
                for row in details
                if row["requested_alias"] == alias
                and (boundary == "overall" or row["boundary"] == boundary)
            ]
            if not selected:
                continue
            p_attack_templates = sum(int(row["permissive_attack_any"]) for row in selected)
            i_attack_templates = sum(int(row["IACG_attack_any"]) for row in selected)
            p_only = sum(
                int(row["permissive_attack_any"] and not row["IACG_attack_any"])
                for row in selected
            )
            i_only = sum(
                int(row["IACG_attack_any"] and not row["permissive_attack_any"])
                for row in selected
            )
            p_low, p_high = wilson_interval(p_attack_templates, len(selected))
            i_low, i_high = wilson_interval(i_attack_templates, len(selected))
            output.append(
                {
                    "requested_alias": alias,
                    "boundary": boundary,
                    "semantic_templates": len(selected),
                    "instances": sum(int(row["instances"]) for row in selected),
                    "valid_instances": sum(int(row["valid_instances"]) for row in selected),
                    "permissive_attack_instances": sum(
                        int(row["permissive_attack_instances"]) for row in selected
                    ),
                    "IACG_attack_instances": sum(
                        int(row["IACG_attack_instances"]) for row in selected
                    ),
                    "permissive_attack_templates": p_attack_templates,
                    "IACG_attack_templates": i_attack_templates,
                    "permissive_template_rate": round(p_attack_templates / len(selected), 6),
                    "permissive_template_wilson_low": round(p_low, 6),
                    "permissive_template_wilson_high": round(p_high, 6),
                    "IACG_template_rate": round(i_attack_templates / len(selected), 6),
                    "IACG_template_wilson_low": round(i_low, 6),
                    "IACG_template_wilson_high": round(i_high, 6),
                    "permissive_only_templates": p_only,
                    "IACG_only_templates": i_only,
                    "template_exact_mcnemar_p": exact_mcnemar(p_only, i_only),
                    "permissive_task_instances": sum(
                        int(row["permissive_task_instances"]) for row in selected
                    ),
                    "IACG_task_instances": sum(
                        int(row["IACG_task_instances"]) for row in selected
                    ),
                }
            )
    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--final", type=Path, nargs="+", required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()

    details = template_rows(read_jsonl(args.final), read_manifest(args.manifest))
    summaries = summary_rows(details)
    write_csv(Path(f"{args.output_prefix}_detail.csv"), details)
    write_csv(Path(f"{args.output_prefix}_summary.csv"), summaries)
    print(
        f"template audit passed: aliases={len({row['requested_alias'] for row in details})} "
        f"clusters={len(details)} instances={sum(int(row['instances']) for row in details)}"
    )


if __name__ == "__main__":
    main()
