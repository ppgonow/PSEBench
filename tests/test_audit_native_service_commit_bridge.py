import importlib.util
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
import run_native_service_commit_bridge as bridge  # noqa: E402

SPEC = importlib.util.spec_from_file_location(
    "audit_native_service_commit_bridge",
    ROOT / "analysis" / "audit_native_service_commit_bridge.py",
)
assert SPEC is not None and SPEC.loader is not None
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def fixture_rows() -> list[dict]:
    rows = []
    digest = "a" * 64
    for alias in bridge.ALIASES:
        for index in range(48):
            for policy in bridge.POLICIES:
                for state in bridge.STATES:
                    committed = int(state == "stable" or policy == "cached-pre-action")
                    rows.append(
                        {
                            "requested_alias": alias,
                            "scenario_id": f"scenario-{index:02d}",
                            "policy": policy,
                            "state": state,
                            "committed": committed,
                            "stale_commit": int(state == "revoked" and committed),
                            "effect_rows": committed,
                            "delivery_attempts": 1,
                            "mutation_observed_active": int(state == "revoked"),
                            "mutation_active_precommit": int(state == "revoked"),
                            "commit_after_mutation_observation": int(state == "revoked"),
                            "mutation_completed": 1,
                            "configured_commit_delay_ms": 10.0,
                            "configured_mutation_hold_ms": 1000.0,
                            "transport_hash_match": 1,
                            "ledger_hash_match": 1,
                            "role_chain_verified": 1,
                            "gateway_total_us": 10.0,
                            "proposal_effect_sha256": digest,
                        }
                    )
    return rows


class AuditNativeServiceCommitBridgeTests(unittest.TestCase):
    def write_fixture(self, root: pathlib.Path, rows: list[dict]) -> tuple[pathlib.Path, ...]:
        attempts = root / "attempts.jsonl"
        raw = root / "raw.jsonl"
        detail = root / "detail.csv"
        summary = root / "summary.csv"
        paired = root / "paired.csv"
        integrity = root / "integrity.csv"
        topology = root / "topology.csv"
        bridge.write_jsonl(
            attempts, [{"status": "complete", **row} for row in rows]
        )
        bridge.write_jsonl(raw, rows)
        bridge.write_csv(detail, rows)
        bridge.write_csv(summary, bridge.summarize(rows))
        bridge.write_csv(paired, bridge.paired(rows))
        bridge.write_csv(integrity, bridge.integrity(rows, True))
        bridge.write_csv(
            topology,
            [
                {
                    "process_count": 3,
                    "distinct_processes": 1,
                    "loopback_only": 1,
                    "health_gate": 1,
                    "authorization_effect_relay_gate": 1,
                    "gateway_effect_relay_gate": 1,
                    "authorization_identity_sha256": "1" * 64,
                    "gateway_identity_sha256": "2" * 64,
                    "effect_identity_sha256": "3" * 64,
                    "unique_identity_commitments": 1,
                }
            ],
        )
        return attempts, raw, detail, summary, paired, integrity, topology

    def test_independent_audit_accepts_complete_fixture(self) -> None:
        with tempfile.TemporaryDirectory(prefix="psebench-bridge-audit-") as directory:
            paths = self.write_fixture(pathlib.Path(directory), fixture_rows())
            checks = audit.audit_files(*paths)
        self.assertTrue(checks)
        self.assertTrue(all(row["passed"] for row in checks))

    def test_independent_audit_detects_hash_gate_failure(self) -> None:
        rows = fixture_rows()
        rows[0]["transport_hash_match"] = 0
        with tempfile.TemporaryDirectory(prefix="psebench-bridge-audit-") as directory:
            paths = self.write_fixture(pathlib.Path(directory), rows)
            checks = audit.audit_files(*paths)
        by_name = {row["check"]: row for row in checks}
        self.assertEqual(by_name["transport_hash_match"]["passed"], 0)


if __name__ == "__main__":
    unittest.main()
