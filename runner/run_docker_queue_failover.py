#!/usr/bin/env python3
"""Run containerized queue partition/crash and consumer failover experiments."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
import os
import pathlib
import secrets
import subprocess
import tempfile
import time
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "runner"))
from commit_binding import CheckContext, issue_receipt, verify_commit  # noqa: E402
from effect_boundary import EffectSpec  # noqa: E402
from run_async_queue_commit import effect_message  # noqa: E402
from run_http_commit_race import load_scenarios  # noqa: E402
from run_multiprocess_commit_race import post_json  # noqa: E402
from run_service_integrated_commit import initial_commit_context  # noqa: E402


IMAGE = "docker.io/library/python@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de"
IMAGE_REFERENCE = "python:3.12-slim"
IMAGE_DIGEST = "sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de"
PROFILES = ("partition-before-commit", "crash-after-commit")
POLICIES = ("check-once", "receipt-bound")


def command(args: list[str], *, check: bool = True, timeout: float = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def wait_health(url: str, role: str, *, timeout: float = 20) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            health = post_json(url, "/health", {})
            if health.get("role") == role:
                return health
        except BaseException as exc:
            last_error = exc
        time.sleep(0.05)
    raise RuntimeError(f"service health failed for {role}: {last_error}")


def published_url(container: str) -> tuple[str, int]:
    output = command(["docker", "port", container, "8080/tcp"]).stdout.strip()
    if not output.startswith("127.0.0.1:"):
        raise RuntimeError(f"service was not published on loopback: {output}")
    port = int(output.rsplit(":", 1)[1])
    return f"http://127.0.0.1:{port}", 1


class DockerCell:
    def __init__(self, root: pathlib.Path, key: bytes, label: str):
        token = secrets.token_hex(4)
        self.prefix = f"psebench-queue-failover-{os.getpid()}-{token}"
        self.network = self.prefix + "-net"
        self.broker = self.prefix + "-broker"
        self.effect = self.prefix + "-effect"
        self.consumer_a = self.prefix + "-consumer-a"
        self.consumer_b = self.prefix + "-consumer-b"
        self.root = root / label
        self.runner_dir = ROOT / "runner"
        self.key = key
        self.broker_url = ""
        self.effect_url = ""
        self.loopback_gates = 0
        self.identity_gate = 0
        self.bridge_gate = 0
        self.network_created = False
        self.started: list[str] = []
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "consumer-a").mkdir()
        (self.root / "consumer-b").mkdir()
        (self.root / "hmac.key").write_bytes(key)

    def _run_container(self, name: str, aliases: list[str], mounts: list[tuple[pathlib.Path, str, bool]], tail: list[str]) -> None:
        args = [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--pull=never",
            "--name",
            name,
            "--network",
            self.network,
        ]
        for alias in aliases:
            args.extend(["--network-alias", alias])
        for source, target, readonly in mounts:
            spec = f"type=bind,src={source},dst={target}"
            if readonly:
                spec += ",readonly"
            args.extend(["--mount", spec])
        args.extend([IMAGE, *tail])
        command(args)
        self.started.append(name)

    def start(self) -> "DockerCell":
        command(["docker", "network", "create", "--driver", "bridge", self.network])
        self.network_created = True
        common = [(self.runner_dir, "/app", True)]
        self._run_published_service(self.broker, "broker", "/state/broker.sqlite")
        self._run_published_service(self.effect, "effect", "/state/effect.sqlite")
        self._run_container(
            self.consumer_a,
            ["consumer-a"],
            common + [(self.root / "consumer-a", "/state", False)],
            ["python", "-c", "import time; time.sleep(3600)"],
        )
        self._run_container(
            self.consumer_b,
            ["consumer-b"],
            common + [(self.root / "consumer-b", "/state", False)],
            ["python", "-c", "import time; time.sleep(3600)"],
        )
        self.broker_url, gate1 = published_url(self.broker)
        self.effect_url, gate2 = published_url(self.effect)
        self.loopback_gates = gate1 + gate2
        wait_health(self.broker_url, "failover-broker")
        wait_health(self.effect_url, "service-integrated-effect")
        identities = {
            command(["docker", "inspect", "--format", "{{.Id}}", name]).stdout.strip()
            for name in (self.broker, self.effect, self.consumer_a, self.consumer_b)
        }
        running = [
            command(
                ["docker", "inspect", "--format", "{{.State.Running}}", name]
            ).stdout.strip()
            for name in (self.consumer_a, self.consumer_b)
        ]
        network = json.loads(
            command(["docker", "network", "inspect", self.network]).stdout
        )[0]
        self.identity_gate = int(len(identities) == 4 and running == ["true", "true"])
        self.bridge_gate = int(
            network.get("Driver") == "bridge"
            and len(network.get("Containers", {})) == 4
        )
        if not self.identity_gate or not self.bridge_gate:
            raise RuntimeError("Docker role identity or bridge membership gate failed")
        return self

    def _run_published_service(self, name: str, role: str, database: str) -> None:
        args = [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--pull=never",
            "--name",
            name,
            "--network",
            self.network,
            "--network-alias",
            role,
            "--publish",
            "127.0.0.1::8080",
            "--mount",
            f"type=bind,src={self.runner_dir},dst=/app,readonly",
            "--mount",
            f"type=bind,src={self.root},dst=/state",
            IMAGE,
            "python",
            "/app/docker_failover_service.py",
            role,
            "--database-path",
            database,
        ]
        if role == "effect":
            args.extend(["--authentication-key-file", "/state/hmac.key"])
        command(args)
        self.started.append(name)

    def exec_worker(self, container: str, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        return command(
            ["docker", "exec", container, "python", "/app/docker_failover_worker.py", *args],
            check=check,
            timeout=120,
        )

    def kill_consumer_a(self) -> None:
        command(["docker", "kill", self.consumer_a])
        self.started.remove(self.consumer_a)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            inspected = command(["docker", "inspect", self.consumer_a], check=False)
            if inspected.returncode != 0:
                return
            time.sleep(0.05)
        raise RuntimeError("killed consumer container was not removed")

    def close(self) -> None:
        errors: list[str] = []
        for name in reversed(self.started):
            result = command(["docker", "rm", "--force", name], check=False)
            if result.returncode:
                errors.append(name)
        self.started.clear()
        if self.network_created:
            result = command(["docker", "network", "rm", self.network], check=False)
            if result.returncode:
                errors.append(self.network)
            else:
                self.network_created = False
        if errors:
            raise RuntimeError(f"Docker cleanup failed: {errors}")

    def __enter__(self) -> "DockerCell":
        try:
            return self.start()
        except Exception:
            self.close()
            raise

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def prepare_case(
    cell: DockerCell,
    key: bytes,
    scenario: dict[str, Any],
    policy: str,
    profile: str,
) -> dict[str, Any]:
    scenario_id = str(scenario["id"])
    trial_id = f"docker-failover:{profile}:{policy}:{scenario_id}"
    race = scenario["commit_race"]
    authorized = EffectSpec(**race["authorized_effect"])
    checked = EffectSpec(**race["checked_effect"])
    final_effect = EffectSpec(**race["commit_effect"])
    check = CheckContext(**race["check_context"])
    context = initial_commit_context(check)
    receipt = issue_receipt(authorized, checked, check, key)
    post_json(
        cell.effect_url,
        "/register",
        {
            "trial_id": trial_id,
            "effect": checked.to_dict(),
            "context": {
                "principal": context.principal,
                "authorization_version": context.authorization_version,
                "committed_at": context.committed_at,
                "confirmation_nonce": context.confirmation_nonce,
                "nonce_consumed": context.nonce_consumed,
            },
        },
    )
    external = verify_commit(receipt, checked, context, key)
    if external.decision != "allow":
        raise RuntimeError(f"check-time receipt unexpectedly blocked: {trial_id}")
    message = effect_message(
        trial_id,
        policy,
        receipt.to_dict(),
        checked if scenario["family"] == "effect-substitution" else final_effect,
    )
    post_json(cell.broker_url, "/enqueue", {"trial_id": trial_id, "message": message})
    substitution_gate = 0
    if scenario["type"] == "attack":
        if scenario["family"] == "effect-substitution":
            post_json(
                cell.broker_url,
                "/substitute",
                {
                    "trial_id": trial_id,
                    "message": effect_message(
                        trial_id, policy, receipt.to_dict(), final_effect
                    ),
                },
            )
            substitution_gate = 1
        post_json(
            cell.effect_url,
            "/mutate",
            {
                "trial_id": trial_id,
                "effect": final_effect.to_dict(),
                "context": race["commit_context"],
            },
        )
    return {
        "scenario": scenario,
        "trial_id": trial_id,
        "external_verify_allow": 1,
        "substitution_gate": substitution_gate,
    }


def load_json(path: pathlib.Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_cell(
    root: pathlib.Path,
    key: bytes,
    scenarios: list[dict[str, Any]],
    profile: str,
    policy: str,
) -> list[dict[str, Any]]:
    label = f"{profile}-{policy}"
    with DockerCell(root, key, label) as cell:
        prepared = [prepare_case(cell, key, scenario, policy, profile) for scenario in scenarios]
        owner_a = "consumer-a"
        owner_b = "consumer-b"
        cell.exec_worker(
            cell.consumer_a,
            [
                "claim-batch",
                "--broker-url",
                "http://broker:8080",
                "--owner",
                owner_a,
                "--count",
                str(len(scenarios)),
                "--state-file",
                "/state/claims.json",
            ],
        )
        partition_gate = 0
        partition_failure_gate = 0
        crash_commit_gate = 0
        a_results: list[dict[str, Any]] = []
        if profile == "partition-before-commit":
            command(["docker", "network", "disconnect", cell.network, cell.consumer_a])
            networks = command(
                ["docker", "inspect", "--format", "{{json .NetworkSettings.Networks}}", cell.consumer_a]
            ).stdout
            partition_gate = int(cell.network not in networks)
            failed = cell.exec_worker(
                cell.consumer_a,
                [
                    "commit-held",
                    "--effect-url",
                    "http://effect:8080",
                    "--state-file",
                    "/state/claims.json",
                    "--result-file",
                    "/state/a-results.json",
                ],
                check=False,
            )
            partition_failure_gate = int(failed.returncode != 0)
            if not partition_gate or not partition_failure_gate:
                raise RuntimeError("partitioned consumer unexpectedly reached effect service")
        elif profile == "crash-after-commit":
            cell.exec_worker(
                cell.consumer_a,
                [
                    "commit-held",
                    "--effect-url",
                    "http://effect:8080",
                    "--state-file",
                    "/state/claims.json",
                    "--result-file",
                    "/state/a-results.json",
                ],
            )
            a_results = load_json(cell.root / "consumer-a" / "a-results.json")
            crash_commit_gate = int(len(a_results) == len(scenarios))
            if not crash_commit_gate:
                raise RuntimeError("consumer A did not complete all pre-crash attempts")
        else:
            raise ValueError(f"unknown profile: {profile}")

        cell.kill_consumer_a()
        inspected = command(["docker", "inspect", cell.consumer_a], check=False)
        consumer_killed_gate = int(inspected.returncode != 0)
        recovered = post_json(cell.broker_url, "/recover-owner", {"owner": owner_a})
        recovery_gate = int(int(recovered["recovered"]) == len(scenarios))
        if not consumer_killed_gate or not recovery_gate:
            raise RuntimeError("consumer stop/recovery happens-before gate failed")

        cell.exec_worker(
            cell.consumer_b,
            [
                "process-batch",
                "--broker-url",
                "http://broker:8080",
                "--effect-url",
                "http://effect:8080",
                "--owner",
                owner_b,
                "--count",
                str(len(scenarios)),
                "--result-file",
                "/state/b-results.json",
            ],
        )
        b_results = load_json(cell.root / "consumer-b" / "b-results.json")
        if len(b_results) != len(scenarios):
            raise RuntimeError("consumer B did not process complete failover batch")
        by_trial_b = {str(row["trial_id"]): row for row in b_results}

        rows: list[dict[str, Any]] = []
        for index, item in enumerate(prepared):
            scenario = item["scenario"]
            trial_id = str(item["trial_id"])
            queue_status = post_json(cell.broker_url, "/status", {"trial_id": trial_id})
            effect_status = post_json(cell.effect_url, "/count", {"trial_id": trial_id})
            b_result = by_trial_b[trial_id]
            a_result = a_results[index] if a_results else None
            attack = scenario["type"] == "attack"
            effect_rows = int(effect_status["effect_rows"])
            mutation_sequence = effect_status["mutation_sequence"]
            effect_sequence = effect_status["effect_sequence"]
            stale = int(
                attack
                and effect_rows == 1
                and mutation_sequence is not None
                and effect_sequence is not None
                and int(mutation_sequence) < int(effect_sequence)
            )
            rows.append(
                {
                    "profile": profile,
                    "policy": policy,
                    "scenario_id": str(scenario["id"]),
                    "family": scenario["family"],
                    "scenario_type": scenario["type"],
                    "invalidation": scenario["commit_race"]["pre_registered_invalidation"],
                    "attack": stale,
                    "task": int(not attack and effect_rows == 1),
                    "committed": effect_rows,
                    "external_verify_allow": item["external_verify_allow"],
                    "substitution_gate": item["substitution_gate"],
                    "consumer_a_claim_gate": 1,
                    "partition_gate": partition_gate,
                    "partition_failure_gate": partition_failure_gate,
                    "crash_commit_gate": crash_commit_gate,
                    "consumer_killed_gate": consumer_killed_gate,
                    "recovery_gate": recovery_gate,
                    "consumer_b_gate": 1,
                    "queue_delivery_attempts": int(queue_status["delivery_count"]),
                    "queue_recovery_rows": int(queue_status["recovery_count"]),
                    "queue_ack_rows": int(queue_status["ack_count"]),
                    "queue_final_acked": int(queue_status["state"] == "acked"),
                    "effect_delivery_attempts": int(effect_status["delivery_attempts"]),
                    "effect_rows": effect_rows,
                    "nonce_rows": int(effect_status["nonce_rows"]),
                    "second_idempotent": int(b_result["idempotent_replay"]),
                    "a_decision": "not_reached" if a_result is None else a_result["decision"],
                    "b_decision": b_result["decision"],
                    "distinct_role_gate": cell.identity_gate,
                    "loopback_publish_gate": int(cell.loopback_gates == 2),
                    "bridge_gate": cell.bridge_gate,
                }
            )
        totals = post_json(cell.broker_url, "/totals", {})
        if (
            int(totals["messages"]) != len(scenarios)
            or int(totals["queued"])
            or int(totals["inflight"])
            or int(totals["acked"]) != len(scenarios)
        ):
            raise RuntimeError(f"failover broker did not drain: {totals}")
        return rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["profile"]), str(row["policy"]))].append(row)
    output: list[dict[str, Any]] = []
    for (profile, policy), selected in sorted(groups.items()):
        attacks = [row for row in selected if row["scenario_type"] == "attack"]
        controls = [row for row in selected if row["scenario_type"] == "benign"]
        output.append(
            {
                "profile": profile,
                "policy": policy,
                "rows": len(selected),
                "attack_n": len(attacks),
                "stale_commits": sum(int(row["attack"]) for row in attacks),
                "control_n": len(controls),
                "control_tasks": sum(int(row["task"]) for row in controls),
                "queue_deliveries": sum(int(row["queue_delivery_attempts"]) for row in selected),
                "effect_attempts": sum(int(row["effect_delivery_attempts"]) for row in selected),
                "effect_rows": sum(int(row["effect_rows"]) for row in selected),
            }
        )
    return output


def integrity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    attacks = [row for row in rows if row["scenario_type"] == "attack"]
    return [
        {
            "rows": len(rows),
            "unique_keys": len({(row["profile"], row["policy"], row["scenario_id"]) for row in rows}),
            "attack_rows": len(attacks),
            "control_rows": len(rows) - len(attacks),
            "stale_commits": sum(int(row["attack"]) for row in attacks),
            "control_tasks": sum(int(row["task"]) for row in rows),
            "partition_rows": sum(row["profile"] == "partition-before-commit" for row in rows),
            "partition_gates": sum(int(row["partition_gate"]) for row in rows),
            "partition_failure_gates": sum(int(row["partition_failure_gate"]) for row in rows),
            "crash_rows": sum(row["profile"] == "crash-after-commit" for row in rows),
            "crash_commit_gates": sum(int(row["crash_commit_gate"]) for row in rows),
            "consumer_killed_gates": sum(int(row["consumer_killed_gate"]) for row in rows),
            "recovery_gates": sum(int(row["recovery_gate"]) for row in rows),
            "consumer_b_gates": sum(int(row["consumer_b_gate"]) for row in rows),
            "substitution_rows": sum(int(row["substitution_gate"]) for row in rows),
            "queue_deliveries": sum(int(row["queue_delivery_attempts"]) for row in rows),
            "queue_recoveries": sum(int(row["queue_recovery_rows"]) for row in rows),
            "queue_acks": sum(int(row["queue_ack_rows"]) for row in rows),
            "queue_final_acked": sum(int(row["queue_final_acked"]) for row in rows),
            "effect_attempts": sum(int(row["effect_delivery_attempts"]) for row in rows),
            "effect_rows": sum(int(row["effect_rows"]) for row in rows),
            "nonce_rows": sum(int(row["nonce_rows"]) for row in rows),
            "second_idempotent_rows": sum(int(row["second_idempotent"]) for row in rows),
            "distinct_role_rows": sum(int(row["distinct_role_gate"]) for row in rows),
            "loopback_publish_rows": sum(int(row["loopback_publish_gate"]) for row in rows),
            "bridge_rows": sum(int(row["bridge_gate"]) for row in rows),
        }
    ]


def validate(rows: list[dict[str, Any]], scenarios: list[dict[str, Any]], *, formal: bool) -> None:
    expected = {
        (profile, policy, str(scenario["id"]))
        for profile in PROFILES
        for policy in POLICIES
        for scenario in scenarios
    }
    observed = {(row["profile"], row["policy"], row["scenario_id"]) for row in rows}
    if len(rows) != len(expected) or observed != expected:
        raise ValueError("Docker queue failover matrix is incomplete or duplicated")
    for row in rows:
        attack = row["scenario_type"] == "attack"
        bound = row["policy"] == "receipt-bound"
        partition = row["profile"] == "partition-before-commit"
        expected_effect = not (bound and attack)
        expected_attempts = 1 if partition else 2
        expected_nonce = int(bound and expected_effect and row["family"] == "confirmation-replay")
        expected_substitution = int(attack and row["family"] == "effect-substitution")
        invariant = (
            int(row["attack"]) == int(attack and not bound)
            and int(row["task"]) == int(not attack and expected_effect)
            and int(row["committed"]) == int(expected_effect)
            and int(row["external_verify_allow"]) == 1
            and int(row["substitution_gate"]) == expected_substitution
            and int(row["consumer_a_claim_gate"]) == 1
            and int(row["partition_gate"]) == int(partition)
            and int(row["partition_failure_gate"]) == int(partition)
            and int(row["crash_commit_gate"]) == int(not partition)
            and int(row["consumer_killed_gate"]) == 1
            and int(row["recovery_gate"]) == 1
            and int(row["consumer_b_gate"]) == 1
            and int(row["queue_delivery_attempts"]) == 2
            and int(row["queue_recovery_rows"]) == 1
            and int(row["queue_ack_rows"]) == 1
            and int(row["queue_final_acked"]) == 1
            and int(row["effect_delivery_attempts"]) == expected_attempts
            and int(row["effect_rows"]) == int(expected_effect)
            and int(row["nonce_rows"]) == expected_nonce
            and int(row["second_idempotent"]) == int(not partition and expected_effect)
            and int(row["distinct_role_gate"]) == 1
            and int(row["loopback_publish_gate"]) == 1
            and int(row["bridge_gate"]) == 1
        )
        if not invariant:
            raise ValueError(f"Docker queue failover row invariant failed: {row}")
    if formal:
        frozen = {
            "rows": 600,
            "unique_keys": 600,
            "attack_rows": 400,
            "control_rows": 200,
            "stale_commits": 200,
            "control_tasks": 200,
            "partition_rows": 300,
            "partition_gates": 300,
            "partition_failure_gates": 300,
            "crash_rows": 300,
            "crash_commit_gates": 300,
            "consumer_killed_gates": 600,
            "recovery_gates": 600,
            "consumer_b_gates": 600,
            "substitution_rows": 80,
            "queue_deliveries": 1200,
            "queue_recoveries": 600,
            "queue_acks": 600,
            "queue_final_acked": 600,
            "effect_attempts": 900,
            "effect_rows": 400,
            "nonce_rows": 20,
            "second_idempotent_rows": 200,
            "distinct_role_rows": 600,
            "loopback_publish_rows": 600,
            "bridge_rows": 600,
        }
        observed_totals = integrity(rows)[0]
        if observed_totals != frozen:
            raise ValueError(f"Docker queue failover totals mismatch: {observed_totals}")


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def pilot_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        next(item for item in scenarios if item["family"] == family and item["type"] == kind)
        for family in sorted({str(item["family"]) for item in scenarios})
        for kind in ("attack", "benign")
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario-dir",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument("--analysis-prefix", type=pathlib.Path)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    inspected = json.loads(command(["docker", "image", "inspect", IMAGE]).stdout)[0]
    if IMAGE_DIGEST not in inspected.get("RepoDigests", [""])[0]:
        repo_digests = inspected.get("RepoDigests", [])
        if not any(item.endswith("@" + IMAGE_DIGEST) for item in repo_digests):
            raise SystemExit(f"pinned image digest not installed: {repo_digests}")
    prefix = args.analysis_prefix or (
        ROOT / "tmp" / "docker_queue_failover_pilot"
        if args.pilot
        else ROOT / "analysis" / "docker_queue_failover"
    )
    output_paths = [
        pathlib.Path(f"{prefix}_detail.csv"),
        pathlib.Path(f"{prefix}_summary.csv"),
        pathlib.Path(f"{prefix}_integrity.csv"),
        pathlib.Path(f"{prefix}_metadata.csv"),
    ]
    if any(path.exists() for path in output_paths) and not args.overwrite:
        raise SystemExit("output exists; pass --overwrite for one fresh complete matrix")
    scenarios = load_scenarios(args.scenario_dir)
    selected = pilot_scenarios(scenarios) if args.pilot else scenarios
    key = secrets.token_bytes(32)
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="psebench-docker-queue-failover-") as directory:
        root = pathlib.Path(directory)
        for profile in PROFILES:
            for policy in POLICIES:
                rows.extend(run_cell(root, key, selected, profile, policy))
        validate(rows, selected, formal=not args.pilot)
    metadata = [
        {
            "image_reference": IMAGE_REFERENCE,
            "image_digest": IMAGE_DIGEST,
            "network_driver": "bridge",
            "host_publish": "127.0.0.1-random",
            "fault_epochs": 4,
            "matrix_rows": len(rows),
        }
    ]
    write_csv(output_paths[0], rows)
    write_csv(output_paths[1], summarize(rows))
    write_csv(output_paths[2], integrity(rows))
    write_csv(output_paths[3], metadata)
    print(
        f"Docker queue failover passed: rows={len(rows)} pilot={int(args.pilot)} "
        f"stale={integrity(rows)[0]['stale_commits']}"
    )


if __name__ == "__main__":
    main()
