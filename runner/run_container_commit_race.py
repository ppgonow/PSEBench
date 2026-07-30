#!/usr/bin/env python3
"""Run the commit-race matrix across three Docker-isolated services."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from container_commit_service import INSTANCE_IDS  # noqa: E402
from run_http_commit_race import load_scenarios  # noqa: E402
from run_multiprocess_commit_race import (  # noqa: E402
    POLICIES,
    paired,
    post_json,
    run_one as run_multiprocess_one,
    summarize,
    validate_complete as validate_multiprocess_complete,
    write_csv,
)


ROLES = ("authorization", "gateway", "effect")


def hash_identifier(value: str) -> str:
    if not value:
        raise ValueError("cannot hash an empty Docker identifier")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def docker_json(arguments: list[str]) -> list[dict[str, Any]]:
    completed = subprocess.run(
        ["docker", *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, list):
        raise ValueError("Docker inspection did not return a JSON list")
    return payload


def topology_from_inspection(
    containers: dict[str, dict[str, Any]],
    networks: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role in ROLES:
        record = containers[role]
        settings = record["NetworkSettings"]
        attached = settings["Networks"]
        if len(attached) != 1:
            raise ValueError(f"{role} must attach to exactly one network")
        network_data = next(iter(attached.values()))
        network_id = str(network_data["NetworkID"])
        network = networks[network_id]
        bindings = settings.get("Ports", {}).get("8080/tcp") or []
        config = record["Config"]
        host_config = record["HostConfig"]
        security_options = host_config.get("SecurityOpt") or []
        cap_drop = host_config.get("CapDrop") or []
        user = str(config.get("User") or "")
        user_name = user.split(":", 1)[0].strip().lower()
        rows.append(
            {
                "role": role,
                "service_instance_id": INSTANCE_IDS[role],
                "container_id_sha256": hash_identifier(str(record["Id"])),
                "network_namespace_sha256": hash_identifier(
                    str(settings["SandboxKey"])
                ),
                "image_id_sha256": hash_identifier(str(record["Image"])),
                "network_id_sha256": hash_identifier(network_id),
                "network_driver": str(network["Driver"]),
                "network_scope": str(network["Scope"]),
                "network_internal": int(bool(network["Internal"])),
                "network_count": len(attached),
                "ip_address": str(network_data["IPAddress"]),
                "published_binding_count": len(bindings),
                "published_host_ip": (
                    str(bindings[0].get("HostIp", "")) if len(bindings) == 1 else ""
                ),
                "published_container_port": "8080/tcp",
                "read_only_rootfs": int(bool(host_config.get("ReadonlyRootfs"))),
                "cap_drop_all": int("ALL" in {str(item).upper() for item in cap_drop}),
                "no_new_privileges": int(
                    any(str(item).lower().startswith("no-new-privileges") for item in security_options)
                ),
                "nonroot_user": int(user_name not in {"", "0", "root"}),
                "running": int(bool(record["State"]["Running"])),
            }
        )
    return rows


def inspect_topology(container_ids: dict[str, str]) -> list[dict[str, Any]]:
    containers: dict[str, dict[str, Any]] = {}
    for role in ROLES:
        records = docker_json(["inspect", container_ids[role]])
        if len(records) != 1:
            raise ValueError(f"Docker returned {len(records)} records for {role}")
        service_label = records[0]["Config"].get("Labels", {}).get(
            "com.docker.compose.service"
        )
        if service_label != role:
            raise ValueError(f"container label mismatch for {role}: {service_label}")
        containers[role] = records[0]
    network_ids = {
        str(next(iter(item["NetworkSettings"]["Networks"].values()))["NetworkID"])
        for item in containers.values()
    }
    networks: dict[str, dict[str, Any]] = {}
    for network_id in network_ids:
        records = docker_json(["network", "inspect", network_id])
        if len(records) != 1:
            raise ValueError("Docker returned an unexpected network record count")
        networks[network_id] = records[0]
    return topology_from_inspection(containers, networks)


def validate_topology(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 3 or {row["role"] for row in rows} != set(ROLES):
        raise ValueError("topology must contain exactly the three service roles")
    distinct_fields = (
        "service_instance_id",
        "container_id_sha256",
        "network_namespace_sha256",
        "ip_address",
    )
    for field in distinct_fields:
        if len({row[field] for row in rows}) != 3:
            raise ValueError(f"topology field is not distinct across roles: {field}")
    if len({row["network_id_sha256"] for row in rows}) != 1:
        raise ValueError("services do not share exactly one Docker network")
    for row in rows:
        if row["network_driver"] != "bridge" or row["network_scope"] != "local":
            raise ValueError(f"unexpected Docker network for {row['role']}")
        if row["network_internal"] != 0 or row["network_count"] != 1:
            raise ValueError(f"network isolation failed for {row['role']}")
        if row["published_binding_count"] != 1:
            raise ValueError(f"unexpected published binding count for {row['role']}")
        if row["published_host_ip"] != "127.0.0.1":
            raise ValueError(f"non-loopback port binding for {row['role']}")
        if not all(
            row[field] == 1
            for field in (
                "read_only_rootfs",
                "cap_drop_all",
                "no_new_privileges",
                "nonroot_user",
                "running",
            )
        ):
            raise ValueError(f"container hardening check failed for {row['role']}")


class ContainerCluster:
    def __init__(self, urls: dict[str, str]):
        self.urls = urls
        self.pids = dict(INSTANCE_IDS)

    def verify_health(self) -> None:
        for role in ROLES:
            health = post_json(self.urls[role], "/health", {})
            if health != {
                "role": role,
                "service_instance_id": INSTANCE_IDS[role],
            }:
                raise ValueError(f"container health identity mismatch for {role}")


def public_identity_row(row: dict[str, Any]) -> dict[str, Any]:
    output = dict(row)
    output["authorization_instance_id"] = output.pop("authorization_pid")
    output["gateway_instance_id"] = output.pop("gateway_pid")
    output["effect_instance_id"] = output.pop("effect_pid")
    return output


def validate_container_complete(
    rows: list[dict[str, Any]], scenarios: list[dict[str, Any]], topology: list[dict[str, Any]]
) -> None:
    validate_topology(topology)
    expected_ids = {str(item["id"]) for item in scenarios}
    expected_keys = {
        (policy, scenario_id) for policy in POLICIES for scenario_id in expected_ids
    }
    actual_keys = {(row["policy"], row["scenario_id"]) for row in rows}
    if len(rows) != 600 or actual_keys != expected_keys:
        raise ValueError("container experiment does not contain the fixed 600-row matrix")
    expected_instances = set(INSTANCE_IDS.values())
    for row in rows:
        observed_instances = {
            row["authorization_instance_id"],
            row["gateway_instance_id"],
            row["effect_instance_id"],
        }
        if observed_instances != expected_instances:
            raise ValueError(f"service identity mismatch for {row['policy']}/{row['scenario_id']}")
        expected_ledger = 1 if row["committed"] else 0
        expected_attempts = (
            2 if row["committed"] and row["duplicate_delivery"] else expected_ledger
        )
        if row["ledger_rows"] != expected_ledger:
            raise ValueError(f"ledger mismatch for {row['policy']}/{row['scenario_id']}")
        if row["delivery_attempts"] != expected_attempts:
            raise ValueError(f"delivery mismatch for {row['policy']}/{row['scenario_id']}")
        if row["scenario_type"] == "attack" and not row["precommit_mutation_active"]:
            raise ValueError(f"causal timing check failed for {row['policy']}/{row['scenario_id']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    for role in ROLES:
        parser.add_argument(f"--{role}-url", required=True)
        parser.add_argument(f"--{role}-container", required=True)
    parser.add_argument(
        "--scenario-dir",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument(
        "--output-root",
        type=pathlib.Path,
        default=ROOT / "results" / "container_commit_race",
    )
    parser.add_argument(
        "--analysis-prefix",
        type=pathlib.Path,
        default=ROOT / "analysis" / "container_commit_race",
    )
    parser.add_argument("--commit-delay-ms", type=float, default=2.0)
    parser.add_argument("--mutation-hold-ms", type=float, default=30.0)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.commit_delay_ms < 0 or args.mutation_hold_ms <= args.commit_delay_ms:
        raise SystemExit("mutation hold must be positive and exceed commit delay")

    urls = {role: getattr(args, f"{role}_url") for role in ROLES}
    container_ids = {role: getattr(args, f"{role}_container") for role in ROLES}
    paths = [
        args.output_root / "container_commit_race.jsonl",
        pathlib.Path(f"{args.analysis_prefix}_detail.csv"),
        pathlib.Path(f"{args.analysis_prefix}_summary.csv"),
        pathlib.Path(f"{args.analysis_prefix}_paired.csv"),
        pathlib.Path(f"{args.analysis_prefix}_topology.csv"),
    ]
    if any(path.exists() for path in paths) and not args.overwrite:
        raise SystemExit("output exists; pass --overwrite for a fresh complete matrix")
    for path in paths:
        if path.exists():
            path.unlink()

    scenarios = load_scenarios(args.scenario_dir)
    topology = inspect_topology(container_ids)
    validate_topology(topology)
    cluster = ContainerCluster(urls)
    cluster.verify_health()

    internal_rows: list[dict[str, Any]] = []
    for policy in POLICIES:
        for scenario in scenarios:
            internal_rows.append(
                run_multiprocess_one(
                    cluster,
                    policy,
                    scenario,
                    commit_delay_ms=args.commit_delay_ms,
                    mutation_hold_ms=args.mutation_hold_ms,
                )
            )
    validate_multiprocess_complete(internal_rows, scenarios, cluster.pids)
    rows = [public_identity_row(row) for row in internal_rows]
    validate_container_complete(rows, scenarios, topology)

    args.output_root.mkdir(parents=True, exist_ok=True)
    paths[0].write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    write_csv(paths[1], rows)
    write_csv(paths[2], summarize(rows))
    write_csv(paths[3], paired(rows))
    write_csv(paths[4], topology)
    print(
        "completed 600 Docker-isolated policy/scenario observations; "
        "topology, timing, retry, and ledger checks passed"
    )


if __name__ == "__main__":
    main()
