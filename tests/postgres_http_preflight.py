"""Explicit HTTP/process preflight for the PostgreSQL critical-window gate."""

from __future__ import annotations

import os
import pathlib
import secrets
import sys
import unittest
import uuid


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from run_http_commit_race import load_scenarios
from run_postgres_integrated_commit import (
    POSTGRES_ATOMIC_HOLD_MS,
    PostgresServiceProcess,
)
from run_service_integrated_commit import run_case


class PostgresHTTPPreflight(unittest.TestCase):
    def test_amended_hold_exposes_blocked_row_lock(self):
        scenarios = load_scenarios(ROOT / "scenarios" / "commit-race-heldout")
        scenario = next(
            item
            for item in scenarios
            if item["id"] == "RACE-authorization-revocation-attack-020"
        )
        key = secrets.token_bytes(32)
        schema = "pse_http_test_" + uuid.uuid4().hex
        with PostgresServiceProcess(
            os.environ["PSEBENCH_POSTGRES_DSN"], schema, key
        ) as service:
            row = run_case(
                service,
                key,
                scenario,
                "service-atomic",
                "critical-window",
                atomic_hold_ms=POSTGRES_ATOMIC_HOLD_MS,
            )
        self.assertEqual(row["verifier_gate"], 1)
        self.assertEqual(row["mutation_requested_after_verify"], 1)
        self.assertEqual(row["mutation_deferred_at_gate"], 1)
        self.assertEqual(row["serialized_commit_before_mutation"], 1)
        self.assertEqual(row["effect_rows"], 1)


if __name__ == "__main__":
    unittest.main()
