#!/usr/bin/env python3
"""Keep the last attempt for each cross-model scenario/policy key."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    rows = {}
    order = []
    for line in args.input.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = (row.get("provider", ""), row.get("model", ""), row.get("policy", ""), row.get("scenario_id", ""))
        if key not in rows:
            order.append(key)
        rows[key] = row

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for key in order:
            f.write(json.dumps(rows[key], ensure_ascii=False, sort_keys=True) + "\n")
    print(f"deduplicated {len(order)} keys from {args.input} to {args.output}")


if __name__ == "__main__":
    main()
