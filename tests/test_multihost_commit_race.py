import copy
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from multihost_commit_service import INSTANCE_IDS, MultiHostIdentityApp
from run_multihost_commit_race import (
    UNIQUE_IDENTITY_FIELDS,
    public_identity_row,
    validate_topology,
)


class DummyApp:
    authorization_url = "http://authorization"
    effect_url = "http://effect"

    def dispatch(self, path, payload, request_received_ns):
        return {
            "service_pid": 9,
            "gateway_pid": 8,
            "value": payload.get("value"),
        }


def topology_rows():
    rows = []
    for index, role in enumerate(("authorization", "gateway", "effect"), 1):
        row = {
            "role": role,
            "service_instance_id": INSTANCE_IDS[role],
            "python_version": "3.11.10",
            "kernel_release": "5.4.0-test",
            "virtualization": "docker",
            "machine_id_sha256": "shared-machine",
            "ssh_proxy_host_sha256": "shared-proxy",
            "transport": "ssh-tunneled-http",
            "service_bind": "remote-loopback",
            "service_health_ok": 1,
            "gateway_relay_probe_ok": 1,
        }
        row.update({field: f"{field}-{index}" for field in UNIQUE_IDENTITY_FIELDS})
        rows.append(row)
    return rows


class MultiHostCommitRaceTests(unittest.TestCase):
    def test_identity_wrapper_replaces_raw_process_ids(self):
        authorization = MultiHostIdentityApp("authorization", DummyApp())
        self.assertEqual(
            authorization.dispatch("/health", {}, 0),
            {
                "role": "authorization",
                "service_instance_id": INSTANCE_IDS["authorization"],
            },
        )
        result = authorization.dispatch("/state", {"value": 4}, 0)
        self.assertEqual(result["service_pid"], INSTANCE_IDS["authorization"])

    def test_topology_accepts_amended_remote_identity_boundary(self):
        validate_topology(topology_rows())

    def test_topology_rejects_shared_boot_identity(self):
        rows = copy.deepcopy(topology_rows())
        rows[2]["boot_id_sha256"] = rows[0]["boot_id_sha256"]
        with self.assertRaisesRegex(ValueError, "boot_id_sha256"):
            validate_topology(rows)

    def test_topology_requires_shared_cloned_machine_id(self):
        rows = copy.deepcopy(topology_rows())
        rows[2]["machine_id_sha256"] = "different-machine"
        with self.assertRaisesRegex(ValueError, "shared cloned machine ID"):
            validate_topology(rows)

    def test_public_rows_use_logical_instance_names(self):
        row = {
            "authorization_pid": 201,
            "gateway_pid": 202,
            "effect_pid": 203,
            "scenario_id": "test",
        }
        public = public_identity_row(row)
        self.assertNotIn("authorization_pid", public)
        self.assertEqual(public["gateway_instance_id"], 202)


if __name__ == "__main__":
    unittest.main()
