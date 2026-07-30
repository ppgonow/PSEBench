import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))

from audit_benchmark_oracle_capabilities import capability_rows, task_inventory  # noqa: E402


class BenchmarkOracleCapabilityAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (
            ROOT / "external" / "official_reproduction" / "agentdojo"
        ).is_dir() or not (
            ROOT / "external" / "official_reproduction" / "agentdojo-core"
        ).is_dir():
            raise unittest.SkipTest(
                "official AgentDojo source checkouts are intentionally not bundled"
            )
        cls.inventory = task_inventory()
        cls.rows = capability_rows(cls.inventory)

    def observed(self, benchmark, capability):
        return next(
            row["observed"]
            for row in self.rows
            if row["benchmark"] == benchmark and row["capability"] == capability
        )

    def test_agentdojo_inventory_includes_post_state_oracles(self):
        self.assertGreater(len(self.inventory), 20)
        self.assertTrue(any(row["uses_post_environment"] for row in self.inventory))
        self.assertEqual(
            self.observed("AgentDojo official v1", "task_post_state_oracle"), 1
        )

    def test_audit_does_not_misstate_agentdojo_as_tool_call_only(self):
        self.assertEqual(
            self.observed("AgentDojo official v1", "current_versioned_authorization"),
            0,
        )
        self.assertEqual(
            self.observed("PSEBench reference harness", "current_versioned_authorization"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
