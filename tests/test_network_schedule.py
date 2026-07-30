import pathlib
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from run_http_commit_race import load_scenarios
from run_multiprocess_commit_race import EffectService, ServiceCluster
import run_network_schedule_matrix
from run_network_schedule_matrix import PROFILES, ScheduleClients, run_case, summarize


class NetworkScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scenarios = load_scenarios(ROOT / "scenarios" / "commit-race-heldout")
        cls.attack = next(row for row in scenarios if row["type"] == "attack")
        cls.control = next(row for row in scenarios if row["type"] == "benign")

    def test_reordered_retry_arrives_out_of_logical_order(self):
        profile = next(row for row in PROFILES if row.name == "reordered-retry")
        with tempfile.TemporaryDirectory() as directory:
            database = pathlib.Path(directory) / "service.sqlite"
            with ServiceCluster(
                database,
                b"k" * 32,
                state_delay_ms=0.0,
                service_delay_ms=0.0,
                pooled_http=True,
                pool_size=4,
            ) as cluster:
                with ScheduleClients(cluster, size=4) as clients:
                    stale = run_case(
                        cluster,
                        clients,
                        self.attack,
                        "check-once",
                        profile,
                        mutation_hold_ms=50.0,
                    )
                    bound = run_case(
                        cluster,
                        clients,
                        self.attack,
                        "receipt-bound",
                        profile,
                        mutation_hold_ms=50.0,
                    )
        self.assertEqual(stale["logical_arrival_order"], "2;1")
        self.assertEqual(stale["attack"], 1)
        self.assertEqual(stale["delivery_attempts"], 2)
        self.assertEqual(stale["ledger_rows"], 1)
        self.assertEqual(bound["logical_arrival_order"], "2;1")
        self.assertEqual(bound["attack"], 0)
        self.assertEqual(bound["delivery_attempts"], 0)
        self.assertEqual(bound["ledger_rows"], 0)

    def test_summary_separates_profiles_and_policies(self):
        rows = []
        for profile in PROFILES:
            for policy in ("check-once", "receipt-bound"):
                for scenario_type in ("attack", "benign"):
                    rows.append(
                        {
                            "profile": profile.name,
                            "policy": policy,
                            "scenario_type": scenario_type,
                            "attack": int(policy == "check-once" and scenario_type == "attack"),
                            "task": int(scenario_type == "benign"),
                            "gateway_attempts": len(profile.attempt_delays_ms),
                            "delivery_attempts": 1,
                            "ledger_rows": 1,
                            "mutation_active_gate": int(scenario_type == "attack"),
                            "reorder_gate": 1,
                            "profile_e2e_us": 1000.0,
                        }
                    )
        summary = summarize(rows)
        self.assertEqual(len(summary), 10)
        self.assertTrue(all(row["rows"] == 2 for row in summary))

    def test_main_uses_a_fresh_database_per_profile(self):
        scenarios = [self.attack, self.control]
        databases = []

        class FakeCluster:
            def __init__(self, database, *_args, **_kwargs):
                databases.append(pathlib.Path(database))
                self.pids = {
                    "authorization": 1,
                    "gateway": 2,
                    "effect": 3,
                }

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

        class FakeClients:
            def __init__(self, *_args, **_kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

        def fake_row(_cluster, _clients, scenario, policy, profile, **_kwargs):
            is_attack = scenario["type"] == "attack"
            allowed = policy == "check-once" or not is_attack
            deliveries = 0
            if allowed:
                deliveries = (
                    2
                    if profile.duplicate_downstream
                    else len(profile.attempt_delays_ms)
                )
            return {
                "profile": profile.name,
                "policy": policy,
                "scenario_id": scenario["id"],
                "family": scenario["family"],
                "scenario_type": scenario["type"],
                "invalidation": scenario["commit_race"]["pre_registered_invalidation"],
                "attack": int(allowed and is_attack),
                "task": int(allowed and not is_attack),
                "committed": int(allowed),
                "valid_at_commit": int(not is_attack),
                "gateway_attempts": len(profile.attempt_delays_ms),
                "logical_arrival_order": "2;1"
                if profile.name == "reordered-retry"
                else "1",
                "reorder_gate": 1,
                "mutation_active_gate": int(is_attack),
                "delivery_attempts": deliveries,
                "ledger_rows": int(allowed),
                "profile_e2e_us": 1.0,
                "arrival_gap_us": 1.0,
                "gateway_max_us": 1.0,
                "role_distinct": 1,
            }

        with tempfile.TemporaryDirectory() as directory:
            output_root = pathlib.Path(directory) / "ignored"
            argv = [
                "run_network_schedule_matrix.py",
                "--pilot",
                "--output-root",
                str(output_root),
                "--overwrite",
            ]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(
                    run_network_schedule_matrix,
                    "load_scenarios",
                    return_value=scenarios,
                ),
                mock.patch.object(
                    run_network_schedule_matrix,
                    "ServiceCluster",
                    FakeCluster,
                ),
                mock.patch.object(
                    run_network_schedule_matrix,
                    "ScheduleClients",
                    FakeClients,
                ),
                mock.patch.object(
                    run_network_schedule_matrix,
                    "run_case",
                    side_effect=fake_row,
                ),
            ):
                run_network_schedule_matrix.main()

        self.assertEqual(len(databases), len(PROFILES))
        self.assertEqual(
            {path.name for path in databases},
            {f"{profile.name}.sqlite" for profile in PROFILES},
        )
        self.assertEqual(len(set(databases)), len(PROFILES))

    def test_effect_counts_serialize_one_sqlite_connection(self):
        class FakeCursor:
            def fetchone(self):
                return (0,)

        class ObservedDatabase:
            def __init__(self):
                self.active = 0
                self.overlapped = False
                self.guard = threading.Lock()

            def execute(self, *_args):
                with self.guard:
                    self.active += 1
                    self.overlapped = self.overlapped or self.active > 1
                time.sleep(0.01)
                with self.guard:
                    self.active -= 1
                return FakeCursor()

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as directory:
            service = EffectService(pathlib.Path(directory) / "service.sqlite", 0.0)
            service.database.close()
            observed = ObservedDatabase()
            service.database = observed
            barrier = threading.Barrier(3)
            errors = []

            def count_worker():
                try:
                    barrier.wait()
                    service.count("same-trial")
                except BaseException as exc:
                    errors.append(exc)

            workers = [threading.Thread(target=count_worker) for _ in range(2)]
            for worker in workers:
                worker.start()
            barrier.wait()
            for worker in workers:
                worker.join()
            service.close()

        self.assertEqual(errors, [])
        self.assertFalse(observed.overlapped)


if __name__ == "__main__":
    unittest.main()
