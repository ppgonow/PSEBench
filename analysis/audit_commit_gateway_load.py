#!/usr/bin/env python3
"""Regenerate commit-gateway load summaries from the released detail CSV."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from benchmark_commit_gateway_load import summarize, write_csv  # noqa: E402


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--detail", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = read_csv(args.detail)
    expected_keys = {
        (policy, concurrency, repeat, index)
        for policy in ("check-once", "receipt-bound")
        for concurrency in (1, 8, 32)
        for repeat in (1, 2, 3)
        for index in range(200)
    }
    observed_keys = {
        (
            row["policy"],
            int(row["concurrency"]),
            int(row["repeat"]),
            int(row["request_index"]),
        )
        for row in rows
    }
    if observed_keys != expected_keys or len(rows) != 3600:
        raise ValueError("load detail does not contain the complete frozen matrix")
    if any(
        int(row["committed"]) != 1
        or int(row["ledger_rows"]) != 1
        or int(row["delivery_attempts"]) != 1
        for row in rows
    ):
        raise ValueError("load detail contains a failed or non-idempotent request")
    write_csv(args.output, summarize(rows))
    print("commit-gateway load audit passed: requests=3600 conditions=6")


if __name__ == "__main__":
    main()
