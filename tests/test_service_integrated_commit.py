import pathlib
import sys
import tempfile
import threading
import time
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from commit_binding import CheckContext, CommitContext, issue_receipt, verify_commit
from effect_boundary import EffectSpec
from run_http_commit_race import load_scenarios
from service_integrated_commit import ServiceIntegratedEffect


KEY = b"s" * 32


class ServiceIntegratedCommitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenarios = load_scenarios(ROOT / "scenarios" / "commit-race-heldout")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.service = ServiceIntegratedEffect(
            pathlib.Path(self.temporary.name) / "service.sqlite", KEY
        )

    def tearDown(self):
        self.temporary.cleanup()

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
        return race, checked, context, receipt

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

    def test_pretransaction_invalidation_blocks_atomic_but_split_commits(self):
        scenario = self.scenario("authorization-revocation", "attack")

        atomic_trial = "atomic-pre"
        race, _checked, _context, receipt = self.register(atomic_trial, scenario)
        self.mutate(atomic_trial, race)
        atomic = self.service.dispatch(
            "/commit-atomic",
            {
                "trial_id": atomic_trial,
                "policy": "service-atomic",
                "receipt": receipt.to_dict(),
                "commit_effect": race["commit_effect"],
            },
            time.perf_counter_ns(),
        )
        self.assertEqual(atomic["decision"], "block")
        self.assertEqual(atomic["effect_rows"], 0)

        split_trial = "split-pre"
        race, checked, context, receipt = self.register(split_trial, scenario)
        self.assertEqual(
            verify_commit(receipt, checked, context, KEY).decision, "allow"
        )
        self.mutate(split_trial, race)
        split = self.service.dispatch(
            "/commit-unverified",
            {
                "trial_id": split_trial,
                "policy": "gateway-split",
                "commit_effect": race["commit_effect"],
            },
            time.perf_counter_ns(),
        )
        self.assertEqual(split["effect_rows"], 1)
        self.assertLess(split["mutation_sequence"], split["effect_sequence"])

    def test_atomic_transaction_serializes_post_verify_mutation(self):
        scenario = self.scenario("principal-switch", "attack")
        trial_id = "atomic-critical"
        race, _checked, _context, receipt = self.register(trial_id, scenario)
        boxes = {}

        def commit_worker():
            boxes["commit"] = self.service.dispatch(
                "/commit-atomic",
                {
                    "trial_id": trial_id,
                    "policy": "service-atomic",
                    "receipt": receipt.to_dict(),
                    "commit_effect": race["checked_effect"],
                    "hold_after_verify_ms": 20.0,
                },
                time.perf_counter_ns(),
            )

        commit_thread = threading.Thread(target=commit_worker)
        commit_thread.start()
        deadline = time.monotonic() + 2
        while self.service._telemetry(trial_id)["verification_completed_ns"] is None:
            if time.monotonic() >= deadline:
                self.fail("atomic verifier gate was not reached")
            time.sleep(0.0005)

        mutation_thread = threading.Thread(
            target=lambda: boxes.setdefault("mutation", self.mutate(trial_id, race))
        )
        mutation_thread.start()
        while self.service._telemetry(trial_id)["mutation_requested_ns"] is None:
            if time.monotonic() >= deadline:
                self.fail("mutation request gate was not reached")
            time.sleep(0.0005)
        self.assertIsNone(
            self.service._telemetry(trial_id)["mutation_lock_acquired_ns"]
        )
        commit_thread.join()
        mutation_thread.join()

        count = self.service.count(trial_id)
        self.assertEqual(boxes["commit"]["decision"], "allow")
        self.assertEqual(count["effect_rows"], 1)
        self.assertLess(count["effect_sequence"], count["mutation_sequence"])

    def test_nonce_consumption_and_duplicate_are_one_transactional_effect(self):
        scenario = self.scenario("confirmation-replay", "benign")
        trial_id = "atomic-confirmation-control"
        race, _checked, _context, receipt = self.register(trial_id, scenario)
        payload = {
            "trial_id": trial_id,
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
        state = self.service.state(trial_id)
        count = self.service.count(trial_id)
        self.assertEqual(first["decision"], "allow")
        self.assertEqual(second["idempotent_replay"], 1)
        self.assertTrue(state["context"]["nonce_consumed"])
        self.assertEqual(count["delivery_attempts"], 2)
        self.assertEqual(count["effect_rows"], 1)
        self.assertEqual(count["nonce_rows"], 1)

    def test_fresh_condition_database_does_not_inherit_nonce_state(self):
        scenario = self.scenario("confirmation-replay", "benign")
        race, _checked, _context, receipt = self.register("condition-one", scenario)
        first = self.service.dispatch(
            "/commit-atomic",
            {
                "trial_id": "condition-one",
                "policy": "service-atomic",
                "receipt": receipt.to_dict(),
                "commit_effect": race["commit_effect"],
            },
            time.perf_counter_ns(),
        )
        self.assertEqual(first["decision"], "allow")

        self.service = ServiceIntegratedEffect(
            pathlib.Path(self.temporary.name) / "second-condition.sqlite", KEY
        )
        race, _checked, _context, receipt = self.register("condition-two", scenario)
        second = self.service.dispatch(
            "/commit-atomic",
            {
                "trial_id": "condition-two",
                "policy": "service-atomic",
                "receipt": receipt.to_dict(),
                "commit_effect": race["commit_effect"],
            },
            time.perf_counter_ns(),
        )
        self.assertEqual(second["decision"], "allow")
        self.assertEqual(second["nonce_rows"], 1)


if __name__ == "__main__":
    unittest.main()
