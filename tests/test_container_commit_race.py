import copy
import pathlib
import sys
import unittest

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from container_commit_service import ContainerIdentityApp, INSTANCE_IDS
from run_container_commit_race import topology_from_inspection, validate_topology


class DummyApp:
    def dispatch(self, path, payload, request_received_ns):
        if path == "/health":
            return {"role": "ignored", "pid": 1}
        return {"service_pid": 1, "value": payload["value"]}


def container_record(role, suffix):
    network_id = "network-id"
    return {
        "Id": f"container-{suffix}",
        "Image": "shared-image",
        "Config": {
            "User": "65532:65532",
            "Labels": {"com.docker.compose.service": role},
        },
        "HostConfig": {
            "ReadonlyRootfs": True,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"],
        },
        "NetworkSettings": {
            "SandboxKey": f"/var/run/docker/netns/{suffix}",
            "Networks": {
                "commit": {
                    "NetworkID": network_id,
                    "IPAddress": f"172.30.0.{suffix}",
                }
            },
            "Ports": {
                "8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": f"50{suffix}"}]
            },
        },
        "State": {"Running": True},
    }


class ContainerCommitRaceTests(unittest.TestCase):
    def setUp(self):
        self.containers = {
            role: container_record(role, index)
            for index, role in enumerate(("authorization", "gateway", "effect"), 2)
        }
        self.networks = {
            "network-id": {
                "Driver": "bridge",
                "Scope": "local",
                "Internal": False,
            }
        }

    def test_identity_wrapper_uses_logical_container_identity(self):
        app = ContainerIdentityApp("authorization", DummyApp())
        self.assertEqual(
            app.dispatch("/health", {}, 0),
            {"role": "authorization", "service_instance_id": INSTANCE_IDS["authorization"]},
        )
        response = app.dispatch("/check", {"value": 7}, 0)
        self.assertEqual(response, {"service_pid": 101, "value": 7})

    def test_topology_parser_accepts_hardened_isolated_services(self):
        rows = topology_from_inspection(self.containers, self.networks)
        validate_topology(rows)
        self.assertEqual(len({row["container_id_sha256"] for row in rows}), 3)
        self.assertEqual(len({row["network_id_sha256"] for row in rows}), 1)

    def test_topology_rejects_non_loopback_publication(self):
        containers = copy.deepcopy(self.containers)
        containers["gateway"]["NetworkSettings"]["Ports"]["8080/tcp"][0][
            "HostIp"
        ] = "0.0.0.0"
        rows = topology_from_inspection(containers, self.networks)
        with self.assertRaisesRegex(ValueError, "non-loopback"):
            validate_topology(rows)

    def test_compose_freezes_security_and_internal_network(self):
        compose = yaml.safe_load(
            (ROOT / "container" / "commit-race" / "compose.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(compose["networks"]["commit_net"]["internal"])
        for role in ("authorization", "gateway", "effect"):
            service = compose["services"][role]
            self.assertTrue(service["read_only"])
            self.assertEqual(service["cap_drop"], ["ALL"])
            self.assertIn("no-new-privileges:true", service["security_opt"])
            self.assertTrue(service["ports"][0].startswith("127.0.0.1:${PSEBENCH_"))

    def test_docker_context_excludes_credentials_and_local_outputs(self):
        patterns = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        self.assertEqual(patterns[0], "*")
        self.assertIn("!runner/**", patterns)
        self.assertNotIn("!.env", patterns)
        self.assertNotIn("!results/**", patterns)


if __name__ == "__main__":
    unittest.main()
