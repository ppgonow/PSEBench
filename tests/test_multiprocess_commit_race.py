import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from run_http_commit_race import load_scenarios
from run_multiprocess_commit_race import ServiceCluster, run_one


class MultiprocessCommitRaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenarios = load_scenarios(ROOT / "scenarios" / "commit-race-heldout")
        cls.attack = next(item for item in cls.scenarios if item["type"] == "attack")
        cls.benign = next(item for item in cls.scenarios if item["type"] == "benign")

    def test_stale_adaptations_fail_and_receipt_binding_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            database = pathlib.Path(directory) / "service.sqlite"
            with ServiceCluster(
                database,
                b"k" * 32,
                state_delay_ms=0.0,
                service_delay_ms=0.0,
            ) as cluster:
                stale = run_one(
                    cluster,
                    "PAuth-style/pre-action",
                    self.attack,
                    commit_delay_ms=1.0,
                    mutation_hold_ms=5.0,
                )
                bound = run_one(
                    cluster,
                    "receipt-bound",
                    self.attack,
                    commit_delay_ms=1.0,
                    mutation_hold_ms=5.0,
                )
                self.assertEqual(len(set(cluster.pids.values())), 3)
            self.assertEqual(stale["attack"], 1)
            self.assertEqual(stale["ledger_rows"], 1)
            self.assertEqual(stale["mutation_before_commit"], 1, stale)
            self.assertEqual(stale["request_overlap"], 1, stale)
            self.assertEqual(bound["attack"], 0)
            self.assertEqual(bound["ledger_rows"], 0)
            self.assertEqual(bound["binding_decision"], "block")
            self.assertEqual(bound["mutation_before_commit"], 1, bound)
            self.assertEqual(bound["request_overlap"], 1, bound)

    def test_effect_service_deduplicates_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            database = pathlib.Path(directory) / "service.sqlite"
            with ServiceCluster(
                database,
                b"k" * 32,
                state_delay_ms=0.0,
                service_delay_ms=0.0,
            ) as cluster:
                row = run_one(
                    cluster,
                    "receipt-bound",
                    self.benign,
                    commit_delay_ms=1.0,
                    mutation_hold_ms=5.0,
                )
            expected_attempts = 2 if row["duplicate_delivery"] else 1
            self.assertEqual(row["task"], 1)
            self.assertEqual(row["ledger_rows"], 1)
            self.assertEqual(row["delivery_attempts"], expected_attempts)


if __name__ == "__main__":
    unittest.main()
