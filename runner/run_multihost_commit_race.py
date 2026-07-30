#!/usr/bin/env python3
"""Run the commit-race matrix on three SSH-tunneled remote instances."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from multihost_commit_service import INSTANCE_IDS  # noqa: E402
from run_http_commit_race import load_scenarios  # noqa: E402
from run_multiprocess_commit_race import (  # noqa: E402
    POLICIES,
    paired,
    post_json,
    run_one,
    summarize,
    validate_complete,
    write_csv,
)


ROLES = ("authorization", "gateway", "effect")
DEFAULT_ALIASES = {
    "authorization": "pse-auth",
    "gateway": "pse-gateway",
    "effect": "pse-effect",
}
SERVICE_FILES = (
    "commit_binding.py",
    "effect_boundary.py",
    "intent_policy.py",
    "multihost_commit_service.py",
    "replay_commit_race.py",
    "run_http_commit_race.py",
    "run_multiprocess_commit_race.py",
)
UNIQUE_IDENTITY_FIELDS = (
    "boot_id_sha256",
    "dmi_product_uuid_sha256",
    "cgroup_identity_sha256",
    "hostname_sha256",
    "pid_namespace_sha256",
    "network_namespace_sha256",
    "uts_namespace_sha256",
    "cpuinfo_sha256",
    "ssh_endpoint_sha256",
)


IDENTITY_PROBE = r"""
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys

def content(path):
    return pathlib.Path(path).read_bytes()

def digest(value):
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()

container_identity = b"\0".join(
    content(path)
    for path in ("/proc/1/cgroup", "/proc/1/cpuset", "/proc/1/mountinfo")
)
virtualization = subprocess.run(
    ["systemd-detect-virt"],
    check=False,
    capture_output=True,
    text=True,
).stdout.strip()
result = {
    "python_version": platform.python_version(),
    "kernel_release": platform.release(),
    "virtualization": virtualization,
    "machine_id_sha256": digest(content("/etc/machine-id").strip()),
    "boot_id_sha256": digest(content("/proc/sys/kernel/random/boot_id").strip()),
    "dmi_product_uuid_sha256": digest(
        content("/sys/class/dmi/id/product_uuid").strip()
    ),
    "cgroup_identity_sha256": digest(container_identity),
    "hostname_sha256": digest(os.uname().nodename),
    "pid_namespace_sha256": digest(os.readlink("/proc/self/ns/pid")),
    "network_namespace_sha256": digest(os.readlink("/proc/self/ns/net")),
    "uts_namespace_sha256": digest(os.readlink("/proc/self/ns/uts")),
    "cpuinfo_sha256": digest(content("/proc/cpuinfo")),
}
print(json.dumps(result, sort_keys=True))
"""


def clean_environment() -> dict[str, str]:
    environment = dict(os.environ)
    sensitive_suffixes = ("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD")
    for name in list(environment):
        if name.endswith(sensitive_suffixes):
            environment.pop(name)
    environment["LC_ALL"] = "C"
    environment["LANG"] = "C"
    return environment


def run_command(
    arguments: list[str],
    *,
    input_text: str | None = None,
    timeout: float = 30,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        check=True,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=clean_environment(),
    )


def ssh_command(
    alias: str,
    remote_arguments: list[str],
    *,
    input_text: str | None = None,
    timeout: float = 30,
) -> subprocess.CompletedProcess[str]:
    remote = shlex.join(remote_arguments)
    return run_command(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            alias,
            remote,
        ],
        input_text=input_text,
        timeout=timeout,
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ssh_endpoint_identity(alias: str) -> dict[str, str]:
    resolved = run_command(["ssh", "-G", alias], timeout=10).stdout.splitlines()
    config: dict[str, str] = {}
    for line in resolved:
        key, _, value = line.partition(" ")
        if key in {"hostname", "port"}:
            config[key] = value.strip()
    if set(config) != {"hostname", "port"}:
        raise ValueError(f"could not resolve SSH endpoint for role alias {alias}")
    return {
        "ssh_proxy_host_sha256": sha256_text(config["hostname"]),
        "ssh_endpoint_sha256": sha256_text(
            f"{config['hostname']}:{config['port']}"
        ),
    }


def probe_topology(aliases: dict[str, str]) -> list[dict[str, Any]]:
    rows = []
    for role in ROLES:
        alias = aliases[role]
        probe = ssh_command(
            alias,
            ["python3", "-c", IDENTITY_PROBE],
            timeout=20,
        )
        identity = json.loads(probe.stdout)
        rows.append(
            {
                "role": role,
                "service_instance_id": INSTANCE_IDS[role],
                **identity,
                **ssh_endpoint_identity(alias),
                "transport": "ssh-tunneled-http",
                "service_bind": "remote-loopback",
                "service_health_ok": 0,
                "gateway_relay_probe_ok": 0,
            }
        )
    return rows


def parse_version(value: str) -> tuple[int, int, int]:
    components = value.split(".")
    return tuple(int(item) for item in components[:3])  # type: ignore[return-value]


def validate_topology(rows: list[dict[str, Any]], *, require_health: bool = True) -> None:
    if len(rows) != 3 or {row["role"] for row in rows} != set(ROLES):
        raise ValueError("topology must contain exactly the three service roles")
    for field in UNIQUE_IDENTITY_FIELDS:
        if len({row[field] for row in rows}) != 3:
            raise ValueError(f"remote identity field is not distinct: {field}")
    if len({row["machine_id_sha256"] for row in rows}) != 1:
        raise ValueError("the amended topology expects one shared cloned machine ID")
    if len({row["ssh_proxy_host_sha256"] for row in rows}) != 1:
        raise ValueError("the amended topology expects one shared SSH proxy hostname")
    for row in rows:
        if parse_version(str(row["python_version"])) < (3, 10, 0):
            raise ValueError(f"Python is older than 3.10 for role {row['role']}")
        if row["virtualization"] != "docker":
            raise ValueError(f"unexpected virtualization for role {row['role']}")
        if row["transport"] != "ssh-tunneled-http":
            raise ValueError(f"unexpected transport for role {row['role']}")
        if row["service_bind"] != "remote-loopback":
            raise ValueError(f"service is not loopback-bound for role {row['role']}")
        if require_health and (
            int(row["service_health_ok"]) != 1
            or int(row["gateway_relay_probe_ok"]) != 1
        ):
            raise ValueError(f"health or relay preflight failed for role {row['role']}")


def free_local_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def free_remote_port(alias: str) -> int:
    program = (
        "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); "
        "print(s.getsockname()[1]); s.close()"
    )
    result = ssh_command(alias, ["python3", "-c", program], timeout=20)
    return int(result.stdout.strip())


class Tunnel:
    def __init__(self, alias: str, forwards: list[str]):
        self.alias = alias
        self.forwards = forwards
        self.process: subprocess.Popen[str] | None = None

    def start(self) -> "Tunnel":
        arguments = [
            "ssh",
            "-N",
            "-T",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "ServerAliveInterval=15",
            "-o",
            "ServerAliveCountMax=3",
        ]
        for forward in self.forwards:
            kind, specification = forward.split("=", 1)
            arguments.extend([kind, specification])
        arguments.append(self.alias)
        self.process = subprocess.Popen(
            arguments,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            env=clean_environment(),
        )
        time.sleep(0.4)
        if self.process.poll() is not None:
            error = self.process.stderr.read().strip() if self.process.stderr else ""
            raise RuntimeError(
                f"SSH forwarding failed for a remote role: {error or 'unknown error'}"
            )
        return self

    def close(self) -> None:
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


class RemoteExperiment:
    def __init__(
        self,
        aliases: dict[str, str],
        *,
        state_delay_ms: float,
        service_delay_ms: float,
    ):
        self.aliases = aliases
        self.state_delay_ms = state_delay_ms
        self.service_delay_ms = service_delay_ms
        self.run_id = f"psebench-multihost-{int(time.time())}-{secrets.token_hex(4)}"
        self.remote_dirs = {
            role: f"/tmp/{self.run_id}-{role}" for role in ROLES
        }
        self.remote_pids: dict[str, int] = {}
        self.remote_ports: dict[str, int] = {}
        self.tunnels: list[Tunnel] = []
        self.urls: dict[str, str] = {}
        self.pids = dict(INSTANCE_IDS)
        self.topology: list[dict[str, Any]] = []
        self.key_directory: tempfile.TemporaryDirectory | None = None

    def prepare(self) -> None:
        self.topology = probe_topology(self.aliases)
        validate_topology(self.topology, require_health=False)
        for role in ROLES:
            directory = self.remote_dirs[role]
            ssh_command(
                self.aliases[role],
                ["mkdir", "-m", "700", directory],
            )
            ssh_command(
                self.aliases[role],
                ["mkdir", "-m", "700", f"{directory}/runner", f"{directory}/runtime"],
            )
            source_files = [str(ROOT / "runner" / name) for name in SERVICE_FILES]
            run_command(
                [
                    "scp",
                    "-q",
                    "-o",
                    "BatchMode=yes",
                    *source_files,
                    f"{self.aliases[role]}:{directory}/runner/",
                ],
                timeout=60,
            )

        self.key_directory = tempfile.TemporaryDirectory(
            prefix="psebench-multihost-key-"
        )
        key_path = pathlib.Path(self.key_directory.name) / "commit_hmac"
        key_path.write_text(secrets.token_hex(32), encoding="ascii")
        key_path.chmod(0o600)
        for role in ("authorization", "gateway"):
            run_command(
                [
                    "scp",
                    "-q",
                    "-o",
                    "BatchMode=yes",
                    str(key_path),
                    f"{self.aliases[role]}:{self.remote_dirs[role]}/runtime/commit_hmac",
                ],
                timeout=30,
            )

    def start_service(self, role: str, extra: list[str]) -> None:
        directory = self.remote_dirs[role]
        ready = f"{directory}/runtime/ready.json"
        program = [
            "python3",
            "runner/multihost_commit_service.py",
            role,
            "--ready-file",
            "runtime/ready.json",
            *extra,
        ]
        shell = (
            f"cd {shlex.quote(directory)} || exit 1; umask 077; "
            f"nohup {shlex.join(program)} >runtime/service.log 2>&1 </dev/null & "
            'service_pid=$!; printf "%s\\n" "$service_pid"'
        )
        started = run_command(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=10",
                self.aliases[role],
                shell,
            ],
            timeout=20,
        )
        self.remote_pids[role] = int(started.stdout.strip())
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            result = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    self.aliases[role],
                    shlex.join(["cat", ready]),
                ],
                capture_output=True,
                text=True,
                env=clean_environment(),
            )
            if result.returncode == 0:
                payload = json.loads(result.stdout)
                if payload != {
                    "bind_scope": "loopback",
                    "port": payload.get("port"),
                    "role": role,
                    "service_instance_id": INSTANCE_IDS[role],
                }:
                    raise RuntimeError(f"invalid ready identity for role {role}")
                self.remote_ports[role] = int(payload["port"])
                return
            time.sleep(0.25)
        raise RuntimeError(f"remote service did not become ready for role {role}")

    def establish(self) -> None:
        self.start_service(
            "authorization",
            [
                "--authentication-key-file",
                "runtime/commit_hmac",
                "--state-delay-ms",
                str(self.state_delay_ms),
            ],
        )
        self.start_service(
            "effect",
            [
                "--database-path",
                "runtime/service.sqlite",
                "--service-delay-ms",
                str(self.service_delay_ms),
            ],
        )

        local_auth = free_local_port()
        local_effect = free_local_port()
        gateway_auth = free_remote_port(self.aliases["gateway"])
        gateway_effect = free_remote_port(self.aliases["gateway"])
        while gateway_auth == gateway_effect:
            gateway_effect = free_remote_port(self.aliases["gateway"])
        self.tunnels.extend(
            [
                Tunnel(
                    self.aliases["authorization"],
                    [
                        f"-L=127.0.0.1:{local_auth}:127.0.0.1:{self.remote_ports['authorization']}"
                    ],
                ).start(),
                Tunnel(
                    self.aliases["effect"],
                    [
                        f"-L=127.0.0.1:{local_effect}:127.0.0.1:{self.remote_ports['effect']}"
                    ],
                ).start(),
            ]
        )
        self.tunnels.append(
            Tunnel(
                self.aliases["gateway"],
                [
                    f"-R=127.0.0.1:{gateway_auth}:127.0.0.1:{local_auth}",
                    f"-R=127.0.0.1:{gateway_effect}:127.0.0.1:{local_effect}",
                ],
            ).start()
        )
        self.start_service(
            "gateway",
            [
                "--authentication-key-file",
                "runtime/commit_hmac",
                "--authorization-url",
                f"http://127.0.0.1:{gateway_auth}",
                "--effect-url",
                f"http://127.0.0.1:{gateway_effect}",
            ],
        )

        local_gateway = free_local_port()
        self.tunnels.append(
            Tunnel(
                self.aliases["gateway"],
                [
                    f"-L=127.0.0.1:{local_gateway}:127.0.0.1:{self.remote_ports['gateway']}",
                ],
            ).start()
        )
        self.urls = {
            "authorization": f"http://127.0.0.1:{local_auth}",
            "gateway": f"http://127.0.0.1:{local_gateway}",
            "effect": f"http://127.0.0.1:{local_effect}",
        }
        self.verify_readiness()

    def verify_readiness(self) -> None:
        for row in self.topology:
            role = row["role"]
            health = post_json(self.urls[role], "/health", {})
            expected = {
                "role": role,
                "service_instance_id": INSTANCE_IDS[role],
            }
            if health != expected:
                raise RuntimeError(f"health identity mismatch for role {role}")
            row["service_health_ok"] = 1
        relay = post_json(self.urls["gateway"], "/downstream-health", {})
        if relay != {
            "authorization_role": "authorization",
            "authorization_instance_id": INSTANCE_IDS["authorization"],
            "effect_role": "effect",
            "effect_instance_id": INSTANCE_IDS["effect"],
        }:
            raise RuntimeError("gateway downstream SSH relay probe failed")
        for row in self.topology:
            row["gateway_relay_probe_ok"] = 1
        validate_topology(self.topology)

    def close(self) -> None:
        for tunnel in reversed(self.tunnels):
            tunnel.close()
        self.tunnels.clear()
        for role, pid in self.remote_pids.items():
            try:
                ssh_command(
                    self.aliases[role],
                    ["kill", "-TERM", str(pid)],
                    timeout=10,
                )
            except Exception:
                pass
        time.sleep(0.2)
        cleanup_program = (
            "import pathlib,shutil,sys; p=pathlib.Path(sys.argv[1]); "
            "assert p.parent == pathlib.Path('/tmp') and "
            "p.name.startswith('psebench-multihost-'); shutil.rmtree(p)"
        )
        for role in ROLES:
            try:
                ssh_command(
                    self.aliases[role],
                    ["python3", "-c", cleanup_program, self.remote_dirs[role]],
                    timeout=20,
                )
            except Exception:
                pass
        self.remote_pids.clear()
        if self.key_directory is not None:
            self.key_directory.cleanup()
            self.key_directory = None

    def __enter__(self) -> "RemoteExperiment":
        try:
            self.prepare()
            self.establish()
            return self
        except BaseException:
            self.close()
            raise

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def public_identity_row(row: dict[str, Any]) -> dict[str, Any]:
    output = dict(row)
    output["authorization_instance_id"] = output.pop("authorization_pid")
    output["gateway_instance_id"] = output.pop("gateway_pid")
    output["effect_instance_id"] = output.pop("effect_pid")
    return output


def validate_multihost_complete(
    rows: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
    topology: list[dict[str, Any]],
) -> None:
    validate_topology(topology)
    expected_ids = {str(item["id"]) for item in scenarios}
    expected_keys = {
        (policy, scenario_id) for policy in POLICIES for scenario_id in expected_ids
    }
    actual_keys = {(row["policy"], row["scenario_id"]) for row in rows}
    if len(rows) != 600 or actual_keys != expected_keys:
        raise ValueError("remote experiment does not contain the fixed 600-row matrix")
    expected_instances = set(INSTANCE_IDS.values())
    for row in rows:
        observed_instances = {
            row["authorization_instance_id"],
            row["gateway_instance_id"],
            row["effect_instance_id"],
        }
        if observed_instances != expected_instances:
            raise ValueError(
                f"service identity mismatch for {row['policy']}/{row['scenario_id']}"
            )
        expected_ledger = 1 if row["committed"] else 0
        expected_attempts = (
            2 if row["committed"] and row["duplicate_delivery"] else expected_ledger
        )
        if row["ledger_rows"] != expected_ledger:
            raise ValueError(f"ledger mismatch for {row['policy']}/{row['scenario_id']}")
        if row["delivery_attempts"] != expected_attempts:
            raise ValueError(
                f"delivery mismatch for {row['policy']}/{row['scenario_id']}"
            )
        if row["scenario_type"] == "attack" and not row[
            "precommit_mutation_active"
        ]:
            raise ValueError(
                f"causal timing check failed for {row['policy']}/{row['scenario_id']}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    for role in ROLES:
        parser.add_argument(
            f"--{role}-alias", default=DEFAULT_ALIASES[role]
        )
    parser.add_argument(
        "--scenario-dir",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument(
        "--output-root",
        type=pathlib.Path,
        default=ROOT / "results" / "multihost_commit_race",
    )
    parser.add_argument(
        "--analysis-prefix",
        type=pathlib.Path,
        default=ROOT / "analysis" / "multihost_commit_race",
    )
    parser.add_argument("--commit-delay-ms", type=float, default=10.0)
    parser.add_argument("--mutation-hold-ms", type=float, default=1000.0)
    parser.add_argument("--state-delay-ms", type=float, default=0.5)
    parser.add_argument("--service-delay-ms", type=float, default=0.5)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.commit_delay_ms != 10.0 or args.mutation_hold_ms != 1000.0:
        raise SystemExit("the frozen remote protocol requires 10 ms and 1000 ms delays")
    if args.state_delay_ms != 0.5 or args.service_delay_ms != 0.5:
        raise SystemExit("the frozen remote protocol requires 0.5 ms service delays")
    if shutil.which("ssh") is None or shutil.which("scp") is None:
        raise SystemExit("ssh and scp are required")

    aliases = {role: getattr(args, f"{role}_alias") for role in ROLES}
    scenarios = load_scenarios(args.scenario_dir)
    output_paths = [
        args.output_root / "multihost_commit_race.jsonl",
        pathlib.Path(f"{args.analysis_prefix}_detail.csv"),
        pathlib.Path(f"{args.analysis_prefix}_summary.csv"),
        pathlib.Path(f"{args.analysis_prefix}_paired.csv"),
        pathlib.Path(f"{args.analysis_prefix}_topology.csv"),
    ]
    if not args.preflight_only and any(path.exists() for path in output_paths):
        raise SystemExit(
            "remote experiment output exists; a frozen amendment is required before retry"
        )

    rows: list[dict[str, Any]] = []
    with RemoteExperiment(
        aliases,
        state_delay_ms=args.state_delay_ms,
        service_delay_ms=args.service_delay_ms,
    ) as cluster:
        if args.preflight_only:
            print(
                "remote preflight passed: three identities, loopback services, "
                "and SSH-relayed gateway paths verified"
            )
            return
        completed = 0
        for policy_index, policy in enumerate(POLICIES, 1):
            print(f"running policy {policy_index}/{len(POLICIES)}: {policy}", flush=True)
            for scenario in scenarios:
                rows.append(
                    run_one(
                        cluster,
                        policy,
                        scenario,
                        commit_delay_ms=args.commit_delay_ms,
                        mutation_hold_ms=args.mutation_hold_ms,
                    )
                )
                completed += 1
                if completed % 25 == 0:
                    print(f"completed {completed}/600 observations", flush=True)
        validate_complete(rows, scenarios, cluster.pids)
        public_rows = [public_identity_row(row) for row in rows]
        topology = [dict(row) for row in cluster.topology]
        validate_multihost_complete(public_rows, scenarios, topology)

    args.output_root.mkdir(parents=True, exist_ok=True)
    output_paths[0].write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in public_rows),
        encoding="utf-8",
    )
    write_csv(output_paths[1], public_rows)
    write_csv(output_paths[2], summarize(public_rows))
    write_csv(output_paths[3], paired(public_rows))
    write_csv(output_paths[4], topology)
    print(
        "completed 600 SSH-tunneled remote-instance observations; "
        "topology, causal timing, retry, and ledger checks passed"
    )


if __name__ == "__main__":
    main()
