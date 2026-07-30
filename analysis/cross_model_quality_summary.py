#!/usr/bin/env python3
"""Summarize valid decisions and transport/parse quality for JSONL runs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / d
    return max(0.0, c - m), min(1.0, c + m)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_jsonl", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    groups = defaultdict(list)
    for line in args.raw_jsonl.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            groups[(row.get("provider", ""), row.get("model", ""), row.get("policy", ""))].append(row)

    out = []
    for (provider, model, policy), rows in sorted(groups.items()):
        errors = [row for row in rows if row.get("api_error") or row.get("parse_error")]
        valid = [row for row in rows if not (row.get("api_error") or row.get("parse_error"))]
        task_yes = sum(bool(row.get("task_action")) for row in valid)
        escalation_yes = sum(bool(row.get("escalation_action")) for row in valid)
        task_lo, task_hi = wilson(task_yes, len(valid))
        esc_lo, esc_hi = wilson(escalation_yes, len(valid))
        out.append(
            {
                "provider": provider,
                "model": model,
                "policy": policy,
                "total_requests": len(rows),
                "valid_requests": len(valid),
                "transport_or_parse_errors": len(errors),
                "error_rate": len(errors) / len(rows) if rows else 0.0,
                "task_yes": task_yes,
                "task_rate": task_yes / len(valid) if valid else 0.0,
                "task_ci_low": task_lo,
                "task_ci_high": task_hi,
                "escalation_yes": escalation_yes,
                "escalation_rate": escalation_yes / len(valid) if valid else 0.0,
                "escalation_ci_low": esc_lo,
                "escalation_ci_high": esc_hi,
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out[0].keys())
        writer.writeheader()
        writer.writerows(out)
    print(f"wrote {len(out)} quality rows to {args.output}")


if __name__ == "__main__":
    main()
