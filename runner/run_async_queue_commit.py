#!/usr/bin/env python3
"""Evaluate enqueue-to-delivery invalidation with a durable async broker."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import multiprocessing
import os
import pathlib
import secrets
import tempfile
import time
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "runner"))
from commit_binding import CheckContext, issue_receipt, verify_commit  # noqa: E402
from durable_async_queue import DurableAsyncQueue  # noqa: E402
from effect_boundary import EffectSpec  # noqa: E402
from run_http_commit_race import load_scenarios  # noqa: E402
from run_multiprocess_commit_race import (  # noqa: E402
    JsonHTTPServer,
    duplicate_delivery_for,
    post_json,
)
from run_service_integrated_commit import (  # noqa: E402
    IntegratedServiceProcess,
    initial_commit_context,
)


POLICIES = ("check-once", "receipt-bound")
PROFILES = ("steady-consumer", "broker-restart")


def serve_broker(
    connection: Any,
    stop_event: Any,
    database_path: str,
) -> None:
    app = DurableAsyncQueue(pathlib.Path(database_path))
    server = JsonHTTPServer(("127.0.0.1", 0), app)
    server.timeout = 0.2
    connection.send({"port": server.server_port, "pid": os.getpid()})
    connection.close()
    try:
        while not stop_event.is_set():
            server.handle_request()
    finally:
        server.server_close()


class DurableBrokerProcess:
    def __init__(self, database_path: pathlib.Path):
        self.database_path = database_path
        self.process: multiprocessing.Process | None = None
        self.stop_event: Any = None
        self.url = ""
        self.pid = -1

    def start(self) -> "DurableBrokerProcess":
        if self.process is not None:
            raise RuntimeError("broker process already started")
        parent, child = multiprocessing.Pipe(duplex=False)
        self.stop_event = multiprocessing.Event()
        self.process = multiprocessing.Process(
            target=serve_broker,
            args=(child, self.stop_event, str(self.database_path)),
            name="psebench-durable-async-broker",
        )
        self.process.start()
        child.close()
        if not parent.poll(10):
            self.process.terminate()
            self.process.join(timeout=5)
            raise RuntimeError("durable async broker did not start")
        ready = parent.recv()
        parent.close()
        self.url = f"http://127.0.0.1:{ready['port']}"
        self.pid = int(ready["pid"])
        health = post_json(self.url, "/health", {})
        if health["role"] != "durable-async-broker" or int(health["pid"]) != self.pid:
            raise RuntimeError("durable async broker identity mismatch")
        return self

    def close(self) -> None:
        if self.process is None:
            return
        self.stop_event.set()
        try:
            post_json(self.url, "/health", {})
        except Exception:
            pass
        self.process.join(timeout=5)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=5)
        if self.process.exitcode:
            raise RuntimeError(
                f"durable async broker exited with {self.process.exitcode}"
            )
        self.process = None

    def __enter__(self) -> "DurableBrokerProcess":
        return self.start()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def effect_message(
    trial_id: str,
    policy: str,
    receipt: dict[str, Any],
    commit_effect: EffectSpec,
) -> dict[str, Any]:
    return {
        "trial_id": trial_id,
        "effect_policy": "gateway-split" if policy == "check-once" else "service-atomic",
        "receipt": receipt,
        "commit_effect": commit_effect.to_dict(),
    }


def prepare_case(
    broker: DurableBrokerProcess,
    service: IntegratedServiceProcess,
    key: bytes,
    scenario: dict[str, Any],
    policy: str,
    profile: str,
) -> dict[str, Any]:
    scenario_id = str(scenario["id"])
    trial_id = f"async-queue:{profile}:{policy}:{scenario_id}"
    race = scenario["commit_race"]
    authorized = EffectSpec(**race["authorized_effect"])
    checked_effect = EffectSpec(**race["checked_effect"])
    final_effect = EffectSpec(**race["commit_effect"])
    check = CheckContext(**race["check_context"])
    stable_context = initial_commit_context(check)
    receipt = issue_receipt(authorized, checked_effect, check, key)
    post_json(
        service.url,
        "/register",
        {
            "trial_id": trial_id,
            "effect": checked_effect.to_dict(),
            "context": {
                "principal": stable_context.principal,
                "authorization_version": stable_context.authorization_version,
                "committed_at": stable_context.committed_at,
                "confirmation_nonce": stable_context.confirmation_nonce,
                "nonce_consumed": stable_context.nonce_consumed,
            },
        },
    )
    external = verify_commit(receipt, checked_effect, stable_context, key)
    if external.decision != "allow":
        raise RuntimeError(f"enqueue-time receipt unexpectedly blocked: {trial_id}")

    initial_message = effect_message(
        trial_id,
        policy,
        receipt.to_dict(),
        checked_effect if scenario["family"] == "effect-substitution" else final_effect,
    )
    enqueued = post_json(
        broker.url,
        "/enqueue",
        {"trial_id": trial_id, "message": initial_message},
    )
    substitution_gate = 0
    is_attack = scenario["type"] == "attack"
    if is_attack:
        if scenario["family"] == "effect-substitution":
            substituted = effect_message(
                trial_id, policy, receipt.to_dict(), final_effect
            )
            post_json(
                broker.url,
                "/substitute",
                {"trial_id": trial_id, "message": substituted},
            )
            substitution_gate = 1
        post_json(
            service.url,
            "/mutate",
            {
                "trial_id": trial_id,
                "effect": final_effect.to_dict(),
                "context": race["commit_context"],
            },
        )

    return {
        "profile": profile,
        "policy": policy,
        "scenario": scenario,
        "trial_id": trial_id,
        "enqueue_sequence": int(enqueued["enqueue_sequence"]),
        "external_verify_allow": int(external.decision == "allow"),
        "enqueue_before_mutation_gate": int(is_attack),
        "substitution_gate": substitution_gate,
        "duplicate_delivery": int(duplicate_delivery_for(scenario_id)),
    }


def effect_commit(
    service: IntegratedServiceProcess,
    message: dict[str, Any],
) -> dict[str, Any]:
    policy = str(message["effect_policy"])
    endpoint = "/commit-unverified" if policy == "gateway-split" else "/commit-atomic"
    return post_json(
        service.url,
        endpoint,
        {
            "trial_id": message["trial_id"],
            "policy": policy,
            "receipt": message["receipt"],
            "commit_effect": message["commit_effect"],
        },
    )


def consume_case(
    broker: DurableBrokerProcess,
    service: IntegratedServiceProcess,
    prepared: dict[str, Any],
    *,
    broker_restart_gate: int,
) -> dict[str, Any]:
    scenario = prepared["scenario"]
    trial_id = str(prepared["trial_id"])
    is_attack = scenario["type"] == "attack"
    started_ns = time.perf_counter_ns()
    first_claim = post_json(broker.url, "/claim", {})
    fifo_gate = int(
        not first_claim.get("empty") and first_claim.get("trial_id") == trial_id
    )
    if not fifo_gate:
        raise RuntimeError(
            f"async queue FIFO mismatch: expected={trial_id} observed={first_claim}"
        )
    responses = [effect_commit(service, first_claim["message"])]
    if prepared["duplicate_delivery"]:
        post_json(broker.url, "/release", {"trial_id": trial_id})
        second_claim = post_json(broker.url, "/claim", {})
        if (
            second_claim.get("empty")
            or second_claim.get("trial_id") != trial_id
            or int(second_claim.get("delivery_number", 0)) != 2
        ):
            raise RuntimeError(f"redelivery gate failed: {trial_id}")
        responses.append(effect_commit(service, second_claim["message"]))
    post_json(broker.url, "/ack", {"trial_id": trial_id})
    consumer_us = (time.perf_counter_ns() - started_ns) / 1000.0

    queue_status = post_json(broker.url, "/status", {"trial_id": trial_id})
    effect_status = post_json(service.url, "/count", {"trial_id": trial_id})
    effect_sequence = effect_status["effect_sequence"]
    mutation_sequence = effect_status["mutation_sequence"]
    effect_rows = int(effect_status["effect_rows"])
    stale_commit = int(
        is_attack
        and effect_rows == 1
        and mutation_sequence is not None
        and effect_sequence is not None
        and int(mutation_sequence) < int(effect_sequence)
    )
    second_idempotent = int(
        len(responses) == 2 and bool(responses[1]["idempotent_replay"])
    )
    return {
        "profile": prepared["profile"],
        "policy": prepared["policy"],
        "scenario_id": str(scenario["id"]),
        "family": scenario["family"],
        "scenario_type": scenario["type"],
        "invalidation": scenario["commit_race"]["pre_registered_invalidation"],
        "attack": stale_commit,
        "task": int(scenario["type"] == "benign" and effect_rows == 1),
        "committed": effect_rows,
        "external_verify_allow": prepared["external_verify_allow"],
        "enqueue_sequence": prepared["enqueue_sequence"],
        "enqueue_before_mutation_gate": prepared["enqueue_before_mutation_gate"],
        "mutation_before_delivery_gate": int(is_attack),
        "substitution_gate": prepared["substitution_gate"],
        "restart_profile": int(prepared["profile"] == "broker-restart"),
        "broker_restart_gate": int(broker_restart_gate),
        "fifo_gate": fifo_gate,
        "duplicate_delivery": prepared["duplicate_delivery"],
        "queue_delivery_attempts": int(queue_status["delivery_count"]),
        "queue_release_rows": int(queue_status["release_count"]),
        "queue_ack_rows": int(queue_status["ack_count"]),
        "queue_final_acked": int(queue_status["state"] == "acked"),
        "effect_delivery_attempts": int(effect_status["delivery_attempts"]),
        "effect_rows": effect_rows,
        "nonce_rows": int(effect_status["nonce_rows"]),
        "second_idempotent": second_idempotent,
        "distinct_roles": int(
            len({os.getpid(), broker.pid, service.pid}) == 3
        ),
        "primary_decision": responses[0]["decision"],
        "consumer_us": round(consumer_us, 3),
    }


def run_cell(
    directory: pathlib.Path,
    key: bytes,
    scenarios: list[dict[str, Any]],
    policy: str,
    profile: str,
) -> list[dict[str, Any]]:
    broker_path = directory / f"broker-{profile}-{policy}.sqlite"
    effect_path = directory / f"effect-{profile}-{policy}.sqlite"
    rows: list[dict[str, Any]] = []
    with IntegratedServiceProcess(effect_path, key) as service:
        if profile == "steady-consumer":
            with DurableBrokerProcess(broker_path) as broker:
                for scenario in scenarios:
                    prepared = prepare_case(
                        broker, service, key, scenario, policy, profile
                    )
                    rows.append(
                        consume_case(
                            broker,
                            service,
                            prepared,
                            broker_restart_gate=0,
                        )
                    )
                totals = post_json(broker.url, "/totals", {})
        elif profile == "broker-restart":
            initial_broker = DurableBrokerProcess(broker_path).start()
            try:
                prepared_rows = [
                    prepare_case(initial_broker, service, key, scenario, policy, profile)
                    for scenario in scenarios
                ]
                initial_pid = initial_broker.pid
            finally:
                initial_broker.close()
            with DurableBrokerProcess(broker_path) as restarted_broker:
                restart_gate = int(restarted_broker.pid != initial_pid)
                if not restart_gate:
                    raise RuntimeError("broker PID did not change across restart")
                for prepared in prepared_rows:
                    rows.append(
                        consume_case(
                            restarted_broker,
                            service,
                            prepared,
                            broker_restart_gate=restart_gate,
                        )
                    )
                totals = post_json(restarted_broker.url, "/totals", {})
        else:
            raise ValueError(f"unknown async queue profile: {profile}")
    if int(totals["queued"]) or int(totals["inflight"]):
        raise RuntimeError(f"async broker did not drain: {totals}")
    if int(totals["acked"]) != len(scenarios):
        raise RuntimeError(f"async broker ack total mismatch: {totals}")
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
                "duplicate_rows": sum(int(row["duplicate_delivery"]) for row in selected),
                "queue_deliveries": sum(
                    int(row["queue_delivery_attempts"]) for row in selected
                ),
                "effect_attempts": sum(
                    int(row["effect_delivery_attempts"]) for row in selected
                ),
                "effect_rows": sum(int(row["effect_rows"]) for row in selected),
                "nonce_rows": sum(int(row["nonce_rows"]) for row in selected),
            }
        )
    return output


def integrity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    attacks = [row for row in rows if row["scenario_type"] == "attack"]
    restart_rows = [row for row in rows if row["restart_profile"]]
    return [
        {
            "rows": len(rows),
            "unique_keys": len(
                {(row["profile"], row["policy"], row["scenario_id"]) for row in rows}
            ),
            "attack_rows": len(attacks),
            "control_rows": len(rows) - len(attacks),
            "stale_commits": sum(int(row["attack"]) for row in attacks),
            "control_tasks": sum(int(row["task"]) for row in rows),
            "attack_enqueue_gates": sum(
                int(row["enqueue_before_mutation_gate"]) for row in attacks
            ),
            "attack_delivery_gates": sum(
                int(row["mutation_before_delivery_gate"]) for row in attacks
            ),
            "substitution_rows": sum(int(row["substitution_gate"]) for row in rows),
            "restart_rows": len(restart_rows),
            "restart_gates": sum(int(row["broker_restart_gate"]) for row in restart_rows),
            "fifo_gates": sum(int(row["fifo_gate"]) for row in rows),
            "duplicate_rows": sum(int(row["duplicate_delivery"]) for row in rows),
            "queue_deliveries": sum(
                int(row["queue_delivery_attempts"]) for row in rows
            ),
            "queue_releases": sum(int(row["queue_release_rows"]) for row in rows),
            "queue_acks": sum(int(row["queue_ack_rows"]) for row in rows),
            "queue_final_acked": sum(int(row["queue_final_acked"]) for row in rows),
            "effect_attempts": sum(
                int(row["effect_delivery_attempts"]) for row in rows
            ),
            "effect_rows": sum(int(row["effect_rows"]) for row in rows),
            "nonce_rows": sum(int(row["nonce_rows"]) for row in rows),
            "second_idempotent_rows": sum(
                int(row["second_idempotent"]) for row in rows
            ),
            "distinct_role_rows": sum(int(row["distinct_roles"]) for row in rows),
        }
    ]


def validate(
    rows: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
    *,
    formal: bool,
) -> None:
    expected = {
        (profile, policy, str(scenario["id"]))
        for profile in PROFILES
        for policy in POLICIES
        for scenario in scenarios
    }
    observed = {
        (str(row["profile"]), str(row["policy"]), str(row["scenario_id"]))
        for row in rows
    }
    if len(rows) != len(expected) or observed != expected:
        raise ValueError("async queue matrix is incomplete or duplicated")
    for row in rows:
        attack = row["scenario_type"] == "attack"
        receipt_bound = row["policy"] == "receipt-bound"
        duplicate = bool(row["duplicate_delivery"])
        expected_effect = not (receipt_bound and attack)
        expected_stale = attack and not receipt_bound
        expected_attempts = 2 if duplicate else 1
        expected_nonce = int(
            receipt_bound and expected_effect and row["family"] == "confirmation-replay"
        )
        expected_substitution = int(attack and row["family"] == "effect-substitution")
        expected_restart = int(row["profile"] == "broker-restart")
        invariant = (
            int(row["attack"]) == int(expected_stale)
            and int(row["task"]) == int(not attack and expected_effect)
            and int(row["committed"]) == int(expected_effect)
            and int(row["external_verify_allow"]) == 1
            and int(row["enqueue_before_mutation_gate"]) == int(attack)
            and int(row["mutation_before_delivery_gate"]) == int(attack)
            and int(row["substitution_gate"]) == expected_substitution
            and int(row["restart_profile"]) == expected_restart
            and int(row["broker_restart_gate"]) == expected_restart
            and int(row["fifo_gate"]) == 1
            and int(row["queue_delivery_attempts"]) == expected_attempts
            and int(row["queue_release_rows"]) == int(duplicate)
            and int(row["queue_ack_rows"]) == 1
            and int(row["queue_final_acked"]) == 1
            and int(row["effect_delivery_attempts"]) == expected_attempts
            and int(row["effect_rows"]) == int(expected_effect)
            and int(row["nonce_rows"]) == expected_nonce
            and int(row["second_idempotent"]) == int(duplicate and expected_effect)
            and int(row["distinct_roles"]) == 1
        )
        if not invariant:
            raise ValueError(f"async queue row invariant failed: {row}")
    if formal:
        frozen = {
            "rows": 600,
            "unique_keys": 600,
            "attack_rows": 400,
            "control_rows": 200,
            "stale_commits": 200,
            "control_tasks": 200,
            "attack_enqueue_gates": 400,
            "attack_delivery_gates": 400,
            "substitution_rows": 80,
            "restart_rows": 300,
            "restart_gates": 300,
            "fifo_gates": 600,
            "duplicate_rows": 120,
            "queue_deliveries": 720,
            "queue_releases": 120,
            "queue_acks": 600,
            "queue_final_acked": 600,
            "effect_attempts": 720,
            "effect_rows": 400,
            "nonce_rows": 20,
            "second_idempotent_rows": 80,
            "distinct_role_rows": 600,
        }
        observed_totals = integrity(rows)[0]
        if observed_totals != frozen:
            raise ValueError(f"async queue frozen totals mismatch: {observed_totals}")


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def pilot_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for family in sorted({str(item["family"]) for item in scenarios}):
        for kind in ("attack", "benign"):
            selected.append(
                next(
                    item
                    for item in scenarios
                    if item["family"] == family
                    and item["type"] == kind
                    and duplicate_delivery_for(str(item["id"]))
                )
            )
    return selected


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
    prefix = args.analysis_prefix
    if prefix is None:
        prefix = (
            ROOT / "tmp" / "async_queue_commit_pilot"
            if args.pilot
            else ROOT / "analysis" / "async_queue_commit"
        )
    output_paths = [
        pathlib.Path(f"{prefix}_detail.csv"),
        pathlib.Path(f"{prefix}_summary.csv"),
        pathlib.Path(f"{prefix}_integrity.csv"),
    ]
    if any(path.exists() for path in output_paths) and not args.overwrite:
        raise SystemExit("output exists; pass --overwrite for one fresh complete matrix")

    scenarios = load_scenarios(args.scenario_dir)
    selected = pilot_scenarios(scenarios) if args.pilot else scenarios
    key = secrets.token_bytes(32)
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="psebench-async-queue-") as directory:
        root = pathlib.Path(directory)
        for profile in PROFILES:
            for policy in POLICIES:
                rows.extend(run_cell(root, key, selected, policy, profile))
        validate(rows, selected, formal=not args.pilot)
    write_csv(output_paths[0], rows)
    write_csv(output_paths[1], summarize(rows))
    write_csv(output_paths[2], integrity(rows))
    print(
        f"async queue matrix passed: rows={len(rows)} pilot={int(args.pilot)} "
        f"stale={integrity(rows)[0]['stale_commits']}"
    )


if __name__ == "__main__":
    main()
