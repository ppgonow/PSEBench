"""Explicit PostgreSQL integration preflight; excluded from default discovery."""

from __future__ import annotations

import os
import pathlib
import sys
import threading
import time
import unittest
import uuid


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from commit_binding import CheckContext, CommitContext, issue_receipt
from effect_boundary import EffectSpec
from postgres_integrated_commit import PostgresIntegratedEffect, drop_postgres_schema
from run_http_commit_race import load_scenarios


KEY = b"p" * 32


class PostgresIntegratedPreflight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["PSEBENCH_POSTGRES_DSN"]
        cls.scenarios = load_scenarios(ROOT / "scenarios" / "commit-race-heldout")

    def setUp(self):
        self.schema = "pse_test_" + uuid.uuid4().hex
        self.service = PostgresIntegratedEffect(self.dsn, self.schema, KEY)

    def tearDown(self):
        drop_postgres_schema(self.dsn, self.schema)

    def scenario(self, family, kind):
        return next(
            item
            for item in self.scenarios
            if item["family"] == family and item["type"] == kind
        )

    def register(self, trial_id, scenario):
        race = scenario["commit_race"]
        checked = EffectSpec(**race["checked_effect"])
        check = CheckContext(**race["check_context"])
        context = CommitContext(
            check.principal,
            check.authorization_version,
            check.checked_at + 1,
            check.confirmation_nonce,
            False,
        )
        receipt = issue_receipt(
            EffectSpec(**race["authorized_effect"]), checked, check, KEY
        )
        self.service.dispatch(
            "/register",
            {
                "trial_id": trial_id,
                "effect": checked.to_dict(),
                "context": {
                    "principal": context.principal,
                    "authorization_version": context.authorization_version,
                    "committed_at": context.committed_at,
                    "confirmation_nonce": context.confirmation_nonce,
                    "nonce_consumed": context.nonce_consumed,
                },
            },
            time.perf_counter_ns(),
        )
        return race, receipt

    def mutate(self, trial_id, race):
        return self.service.dispatch(
            "/mutate",
            {
                "trial_id": trial_id,
                "effect": race["commit_effect"],
                "context": race["commit_context"],
            },
            time.perf_counter_ns(),
        )

    def test_pretransaction_split_and_atomic_diverge(self):
        scenario = self.scenario("authorization-revocation", "attack")
        race, receipt = self.register("atomic-pre", scenario)
        self.mutate("atomic-pre", race)
        atomic = self.service.dispatch(
            "/commit-atomic",
            {
                "trial_id": "atomic-pre",
                "policy": "service-atomic",
                "receipt": receipt.to_dict(),
                "commit_effect": race["commit_effect"],
            },
            time.perf_counter_ns(),
        )
        self.assertEqual((atomic["decision"], atomic["effect_rows"]), ("block", 0))

        race, receipt = self.register("split-pre", scenario)
        self.mutate("split-pre", race)
        split = self.service.dispatch(
            "/commit-unverified",
            {
                "trial_id": "split-pre",
                "policy": "gateway-split",
                "receipt": receipt.to_dict(),
                "commit_effect": race["commit_effect"],
            },
            time.perf_counter_ns(),
        )
        self.assertEqual(split["effect_rows"], 1)
        self.assertLess(split["mutation_sequence"], split["effect_sequence"])

    def test_row_lock_serializes_post_verify_mutation(self):
        scenario = self.scenario("principal-switch", "attack")
        race, receipt = self.register("atomic-critical", scenario)
        boxes = {}

        def commit_worker():
            boxes["commit"] = self.service.dispatch(
                "/commit-atomic",
                {
                    "trial_id": "atomic-critical",
                    "policy": "service-atomic",
                    "receipt": receipt.to_dict(),
                    "commit_effect": race["checked_effect"],
                    "hold_after_verify_ms": 20.0,
                },
                time.perf_counter_ns(),
            )

        commit_thread = threading.Thread(target=commit_worker)
        commit_thread.start()
        deadline = time.monotonic() + 3
        while self.service._telemetry("atomic-critical")["verification_completed_ns"] is None:
            if time.monotonic() >= deadline:
                self.fail("PostgreSQL verifier gate was not reached")
            time.sleep(0.0005)
        mutation_thread = threading.Thread(
            target=lambda: boxes.setdefault(
                "mutation", self.mutate("atomic-critical", race)
            )
        )
        mutation_thread.start()
        while self.service._telemetry("atomic-critical")["mutation_requested_ns"] is None:
            if time.monotonic() >= deadline:
                self.fail("PostgreSQL mutation request gate was not reached")
            time.sleep(0.0005)
        self.assertIsNone(
            self.service._telemetry("atomic-critical")["mutation_lock_acquired_ns"]
        )
        commit_thread.join()
        mutation_thread.join()
        count = self.service.count("atomic-critical")
        self.assertLess(count["effect_sequence"], count["mutation_sequence"])

    def test_nonce_and_duplicate_share_one_effect(self):
        scenario = self.scenario("confirmation-replay", "benign")
        race, receipt = self.register("atomic-confirmation", scenario)
        payload = {
            "trial_id": "atomic-confirmation",
            "policy": "service-atomic",
            "receipt": receipt.to_dict(),
            "commit_effect": race["commit_effect"],
        }
        first = self.service.dispatch(
            "/commit-atomic", payload, time.perf_counter_ns()
        )
        second = self.service.dispatch(
            "/commit-atomic", payload, time.perf_counter_ns()
        )
        count = self.service.count("atomic-confirmation")
        self.assertEqual(first["decision"], "allow")
        self.assertEqual(second["idempotent_replay"], 1)
        self.assertEqual(
            (count["delivery_attempts"], count["effect_rows"], count["nonce_rows"]),
            (2, 1, 1),
        )


if __name__ == "__main__":
    unittest.main()
