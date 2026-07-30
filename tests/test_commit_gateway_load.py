import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from benchmark_commit_gateway_load import run_condition, summarize
from run_http_commit_race import load_scenarios
from run_multiprocess_commit_race import PersistentJsonPool, ServiceCluster


class CommitGatewayLoadTests(unittest.TestCase):
    def test_summary_uses_repeat_throughput_and_request_latency(self):
        rows = []
        for policy in ("check-once", "receipt-bound"):
            for repeat, throughput in ((1, 100.0), (2, 120.0), (3, 80.0)):
                for index in range(2):
                    rows.append(
                        {
                            "policy": policy,
                            "concurrency": 1,
                            "repeat": repeat,
                            "committed": 1,
                            "condition_throughput_rps": throughput,
                            "client_e2e_us": 1000 + index,
                            "gateway_total_us": 500 + index,
                            "auth_query_us": 10 if policy == "receipt-bound" else 0,
                            "service_call_us": 300 + index,
                        }
                    )
        summary = summarize(rows)
        self.assertEqual(len(summary), 2)
        self.assertEqual(summary[0]["throughput_median_rps"], 100.0)
        self.assertEqual(summary[0]["requests"], 6)
        self.assertEqual(summary[0]["committed"], 6)

    def test_persistent_transport_commits_concurrent_stable_requests(self):
        scenario = next(
            row
            for row in load_scenarios(ROOT / "scenarios" / "commit-race-heldout")
            if row["type"] == "benign"
        )
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
                with PersistentJsonPool(cluster.urls["authorization"], 4) as auth_pool:
                    with PersistentJsonPool(cluster.urls["gateway"], 4) as gateway_pool:
                        rows = run_condition(
                            cluster,
                            scenario,
                            policy="receipt-bound",
                            concurrency=4,
                            repeat=1,
                            requests=8,
                            warmup=2,
                            authorization_pool=auth_pool,
                            gateway_pool=gateway_pool,
                        )
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(row["committed"] == 1 for row in rows))
        self.assertEqual(len({row["trial_id"] for row in rows}), 8)


if __name__ == "__main__":
    unittest.main()
import tempfile
