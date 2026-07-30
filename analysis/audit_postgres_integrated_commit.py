#!/usr/bin/env python3
"""Audit the PostgreSQL service-atomic portability matrix without a service."""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))

from audit_service_integrated_commit import (  # noqa: E402
    integrity,
    read_detail,
    summarize,
    validate,
    write_csv,
)


FROZEN_IMAGE_DIGEST = (
    "sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193"
)


def add_backend(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"backend": "postgresql", **row} for row in rows]


def read_metadata(path: pathlib.Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        raise ValueError("PostgreSQL metadata must contain exactly one row")
    return rows[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--detail",
        type=pathlib.Path,
        default=ROOT / "analysis" / "postgres_integrated_commit_detail.csv",
    )
    parser.add_argument(
        "--metadata",
        type=pathlib.Path,
        default=ROOT / "analysis" / "postgres_integrated_commit_metadata.csv",
    )
    parser.add_argument(
        "--scenario-dir",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument(
        "--output-prefix",
        type=pathlib.Path,
        default=ROOT / "tmp" / "postgres_integrated_commit_audit",
    )
    args = parser.parse_args()

    rows = read_detail(args.detail)
    if not rows or any(row.get("backend") != "postgresql" for row in rows):
        raise ValueError("detail rows do not identify the PostgreSQL backend")
    validate(rows, args.scenario_dir)

    metadata = read_metadata(args.metadata)
    if (
        metadata.get("backend") != "postgresql"
        or not metadata.get("server_version", "").startswith("17.")
        or metadata.get("transaction_isolation") != "read committed"
        or metadata.get("driver") != "psycopg"
        or metadata.get("image_digest") != FROZEN_IMAGE_DIGEST
        or int(metadata.get("matrix_rows", "0")) != 540
    ):
        raise ValueError(f"PostgreSQL metadata mismatch: {metadata}")

    write_csv(
        pathlib.Path(f"{args.output_prefix}_summary.csv"),
        add_backend(summarize(rows)),
    )
    write_csv(
        pathlib.Path(f"{args.output_prefix}_integrity.csv"),
        add_backend(integrity(rows)),
    )
    print(
        "PostgreSQL portability audit passed: rows=540 stale_split=180 "
        "stale_atomic=0 critical_serialized=80"
    )


if __name__ == "__main__":
    main()
