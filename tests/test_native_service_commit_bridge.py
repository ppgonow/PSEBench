import pathlib
import secrets
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
import run_native_service_commit_bridge as bridge  # noqa: E402


class NativeServiceCommitBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.proposals = bridge.load_frozen_proposals(
            ROOT / "analysis",
            ROOT / "scenarios" / "same-tool-native-holdout" / "MANIFEST.csv",
        )

    def test_frozen_proposals_are_balanced(self) -> None:
        self.assertEqual(len(self.proposals), 192)
        self.assertEqual(
            {alias: sum(row["requested_alias"] == alias for row in self.proposals) for alias in bridge.ALIASES},
            {alias: 48 for alias in bridge.ALIASES},
        )

    def test_three_process_four_cell_smoke(self) -> None:
        with tempfile.TemporaryDirectory(prefix="psebench-native-bridge-test-") as directory:
            database = pathlib.Path(directory) / "effect.sqlite"
            with bridge.NativeServiceCluster(database, secrets.token_bytes(32)) as cluster:
                topology = cluster.topology(secrets.token_bytes(32))
                self.assertEqual(topology["distinct_processes"], 1)
                rows = [
                    bridge.run_case(
                        cluster,
                        self.proposals[0],
                        policy,
                        state,
                        mutation_hold_ms=50.0,
                        commit_delay_ms=5.0,
                    )
                    for policy in bridge.POLICIES
                    for state in bridge.STATES
                ]
        observed = {
            (row["policy"], row["state"]): (row["decision"], row["effect_rows"])
            for row in rows
        }
        self.assertEqual(observed[("cached-pre-action", "stable")], ("allow", 1))
        self.assertEqual(observed[("cached-pre-action", "revoked")], ("allow", 1))
        self.assertEqual(observed[("receipt-bound", "stable")], ("allow", 1))
        self.assertEqual(observed[("receipt-bound", "revoked")], ("block", 0))
        self.assertTrue(all(row["transport_hash_match"] for row in rows))
        self.assertTrue(all(row["ledger_hash_match"] for row in rows))
        self.assertTrue(all(row["role_chain_verified"] for row in rows))
        revoked = [row for row in rows if row["state"] == "revoked"]
        self.assertTrue(all(row["mutation_observed_active"] for row in revoked))
        self.assertTrue(all(row["mutation_active_precommit"] for row in revoked))

    def test_hold_must_exceed_commit_delay(self) -> None:
        with tempfile.TemporaryDirectory(prefix="psebench-native-bridge-test-") as directory:
            with bridge.NativeServiceCluster(
                pathlib.Path(directory) / "effect.sqlite", secrets.token_bytes(32)
            ) as cluster:
                with self.assertRaisesRegex(ValueError, "hold must exceed"):
                    bridge.run_case(
                        cluster,
                        self.proposals[0],
                        "receipt-bound",
                        "revoked",
                        mutation_hold_ms=5.0,
                        commit_delay_ms=5.0,
                    )


if __name__ == "__main__":
    unittest.main()
