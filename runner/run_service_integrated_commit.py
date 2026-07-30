#!/usr/bin/env python3
"""Evaluate transaction-bound receipt verification in the effect service."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
import multiprocessing
import os
import pathlib
import secrets
import tempfile
import threading
import time
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "runner"))
from commit_binding import (  # noqa: E402
    CheckContext,
    CommitContext,
    issue_receipt,
    verify_commit,
)
from effect_boundary import EffectSpec  # noqa: E402
from run_http_commit_race import EXPECTED_FAMILIES, load_scenarios  # noqa: E402
from run_multiprocess_commit_race import (  # noqa: E402
    JsonHTTPServer,
    duplicate_delivery_for,
    post_json,
)
from service_integrated_commit import ServiceIntegratedEffect  # noqa: E402


POLICIES = ("gateway-split", "service-atomic")
SCHEDULES = ("pre-transaction", "critical-window")
CRITICAL_FAMILIES = tuple(
    family for family in sorted(EXPECTED_FAMILIES) if family != "effect-substitution"
)
ATOMIC_HOLD_MS = 10.0


def serve_service(
    connection: Any,
    stop_event: Any,
    database_path: str,
    authentication_key: bytes,
) -> None:
    app = ServiceIntegratedEffect(pathlib.Path(database_path), authentication_key)
    server = JsonHTTPServer(("127.0.0.1", 0), app)
    server.timeout = 0.2
    connection.send({"port": server.server_port, "pid": os.getpid()})
    connection.close()
    try:
        while not stop_event.is_set():
            server.handle_request()
    finally:
        server.server_close()


class IntegratedServiceProcess:
    def __init__(self, database_path: pathlib.Path, authentication_key: bytes):
        self.database_path = database_path
        self.authentication_key = authentication_key
        self.process: multiprocessing.Process | None = None
        self.stop_event: Any = None
        self.url = ""
        self.pid = -1

    def start(self) -> "IntegratedServiceProcess":
        parent, child = multiprocessing.Pipe(duplex=False)
        self.stop_event = multiprocessing.Event()
        self.process = multiprocessing.Process(
            target=serve_service,
            args=(
                child,
                self.stop_event,
                str(self.database_path),
                self.authentication_key,
            ),
            name="psebench-service-integrated-effect",
        )
        self.process.start()
        child.close()
        if not parent.poll(10):
            self.process.terminate()
            self.process.join(timeout=5)
            raise RuntimeError("service-integrated effect process did not start")
        ready = parent.recv()
        parent.close()
        self.url = f"http://127.0.0.1:{ready['port']}"
        self.pid = int(ready["pid"])
        health = post_json(self.url, "/health", {})
        if health["role"] != "service-integrated-effect" or int(health["pid"]) != self.pid:
            raise RuntimeError("service-integrated effect identity mismatch")
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
                f"service-integrated effect process exited with {self.process.exitcode}"
            )

    def __enter__(self) -> "IntegratedServiceProcess":
        return self.start()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def initial_commit_context(check: CheckContext) -> CommitContext:
    return CommitContext(
        principal=check.principal,
        authorization_version=check.authorization_version,
        committed_at=min(check.expires_at, check.checked_at + 1),
        confirmation_nonce=check.confirmation_nonce,
        nonce_consumed=False,
    )


def wait_status(
    service_url: str,
    trial_id: str,
    field: str,
    *,
    timeout: float = 10.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        status = post_json(service_url, "/status", {"trial_id": trial_id})
        if status.get(field) is not None:
            return status
        if time.monotonic() >= deadline:
            raise TimeoutError(f"timed out waiting for {field}: {trial_id}")
        time.sleep(0.0005)


def run_case(
    service: IntegratedServiceProcess,
    key: bytes,
    scenario: dict[str, Any],
    policy: str,
    schedule: str,
    *,
    atomic_hold_ms: float = ATOMIC_HOLD_MS,
) -> dict[str, Any]:
    if atomic_hold_ms < 0 or atomic_hold_ms > 50:
        raise ValueError("atomic hold must be between 0 and 50 ms")
    scenario_id = str(scenario["id"])
    trial_id = f"service-integrated:{schedule}:{policy}:{scenario_id}"
    race = scenario["commit_race"]
    authorized = EffectSpec(**race["authorized_effect"])
    checked_effect = EffectSpec(**race["checked_effect"])
    final_effect = EffectSpec(**race["commit_effect"])
    check = CheckContext(**race["check_context"])
    stable_context = initial_commit_context(check)
    receipt = issue_receipt(authorized, checked_effect, check, key)
    receipt_payload = receipt.to_dict()
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
        raise RuntimeError(f"check-time receipt unexpectedly blocked: {trial_id}")

    is_attack = scenario["type"] == "attack"
    mutation_payload = {
        "trial_id": trial_id,
        "effect": final_effect.to_dict(),
        "context": race["commit_context"],
    }
    endpoint = "/commit-atomic" if policy == "service-atomic" else "/commit-unverified"
    commit_payload = {
        "trial_id": trial_id,
        "policy": policy,
        "receipt": receipt_payload,
        "commit_effect": final_effect.to_dict(),
        "hold_after_verify_ms": 0.0,
    }
    mutation_applied_before_request = 0
    verifier_gate = 0
    mutation_requested_after_verify = 0
    mutation_deferred_at_gate = 0
    responses: list[dict[str, Any]] = []
    started_ns = time.perf_counter_ns()

    if schedule == "pre-transaction":
        if is_attack:
            post_json(service.url, "/mutate", mutation_payload)
            status = wait_status(service.url, trial_id, "mutation_applied_ns")
            mutation_applied_before_request = int(status["mutation_applied_ns"] is not None)
        responses.append(post_json(service.url, endpoint, commit_payload))
    elif schedule == "critical-window":
        if scenario["family"] not in CRITICAL_FAMILIES:
            raise ValueError(f"family is not valid for critical window: {scenario['family']}")
        if is_attack and policy == "service-atomic":
            boxes: dict[str, dict[str, Any]] = {}
            errors: list[BaseException] = []
            commit_payload["hold_after_verify_ms"] = atomic_hold_ms

            def commit_worker() -> None:
                try:
                    boxes["commit"] = post_json(service.url, endpoint, commit_payload)
                except BaseException as exc:  # pragma: no cover - formal failure path
                    errors.append(exc)

            def mutation_worker() -> None:
                try:
                    boxes["mutation"] = post_json(service.url, "/mutate", mutation_payload)
                except BaseException as exc:  # pragma: no cover - formal failure path
                    errors.append(exc)

            commit_thread = threading.Thread(target=commit_worker)
            commit_thread.start()
            status = wait_status(service.url, trial_id, "verification_completed_ns")
            verifier_gate = int(
                status.get("effect_transaction_started_ns") is not None
                and status.get("effect_transaction_committed_ns") is None
            )
            mutation_thread = threading.Thread(target=mutation_worker)
            mutation_thread.start()
            status = wait_status(service.url, trial_id, "mutation_requested_ns")
            mutation_requested_after_verify = 1
            mutation_deferred_at_gate = int(
                status.get("mutation_lock_acquired_ns") is None
                and status.get("effect_transaction_committed_ns") is None
            )
            commit_thread.join()
            mutation_thread.join()
            if errors:
                raise RuntimeError(f"critical-window request failed: {errors}")
            responses.append(boxes["commit"])
        else:
            if is_attack:
                post_json(service.url, "/mutate", mutation_payload)
                status = wait_status(service.url, trial_id, "mutation_applied_ns")
                mutation_applied_before_request = int(
                    status["mutation_applied_ns"] is not None
                )
                mutation_requested_after_verify = 1
            responses.append(post_json(service.url, endpoint, commit_payload))
    else:
        raise ValueError(f"unknown schedule: {schedule}")

    duplicate = duplicate_delivery_for(scenario_id)
    if duplicate:
        responses.append(post_json(service.url, endpoint, commit_payload))
    elapsed_us = (time.perf_counter_ns() - started_ns) / 1000.0
    counts = post_json(service.url, "/count", {"trial_id": trial_id})
    effect_sequence = counts["effect_sequence"]
    mutation_sequence = counts["mutation_sequence"]
    effect_rows = int(counts["effect_rows"])
    stale_commit = int(
        effect_rows == 1
        and mutation_sequence is not None
        and int(mutation_sequence) < int(effect_sequence)
    )
    serialized_commit_before_mutation = int(
        effect_rows == 1
        and mutation_sequence is not None
        and int(effect_sequence) < int(mutation_sequence)
    )
    second_idempotent = int(
        len(responses) == 2 and bool(responses[1]["idempotent_replay"])
    )
    return {
        "schedule": schedule,
        "policy": policy,
        "scenario_id": scenario_id,
        "family": scenario["family"],
        "scenario_type": scenario["type"],
        "invalidation": race["pre_registered_invalidation"],
        "attack": stale_commit,
        "task": int(scenario["type"] == "benign" and effect_rows == 1),
        "committed": effect_rows,
        "valid_at_linearization": int(effect_rows == 1 and not stale_commit),
        "authorized_attack_commit": int(is_attack and effect_rows == 1 and not stale_commit),
        "external_verify_allow": int(external.decision == "allow"),
        "mutation_applied_before_request": mutation_applied_before_request,
        "verifier_gate": verifier_gate,
        "mutation_requested_after_verify": mutation_requested_after_verify,
        "mutation_deferred_at_gate": mutation_deferred_at_gate,
        "serialized_commit_before_mutation": serialized_commit_before_mutation,
        "duplicate_delivery": int(duplicate),
        "delivery_attempts": int(counts["delivery_attempts"]),
        "effect_rows": effect_rows,
        "nonce_rows": int(counts["nonce_rows"]),
        "second_idempotent": second_idempotent,
        "role_distinct": int(service.pid != os.getpid()),
        "primary_decision": responses[0]["decision"],
        "client_us": round(elapsed_us, 3),
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["schedule"]), str(row["policy"]))].append(row)
    output: list[dict[str, Any]] = []
    for (schedule, policy), selected in sorted(groups.items()):
        attacks = [row for row in selected if row["scenario_type"] == "attack"]
        controls = [row for row in selected if row["scenario_type"] == "benign"]
        output.append(
            {
                "schedule": schedule,
                "policy": policy,
                "rows": len(selected),
                "attack_n": len(attacks),
                "stale_commits": sum(int(row["attack"]) for row in attacks),
                "control_n": len(controls),
                "control_tasks": sum(int(row["task"]) for row in controls),
                "authorized_attack_commits": sum(
                    int(row["authorized_attack_commit"]) for row in attacks
                ),
                "delivery_attempts": sum(int(row["delivery_attempts"]) for row in selected),
                "effect_rows": sum(int(row["effect_rows"]) for row in selected),
                "nonce_rows": sum(int(row["nonce_rows"]) for row in selected),
            }
        )
    return output


def integrity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    attacks = [row for row in rows if row["scenario_type"] == "attack"]
    controls = [row for row in rows if row["scenario_type"] == "benign"]
    critical_atomic_attacks = [
        row
        for row in attacks
        if row["schedule"] == "critical-window" and row["policy"] == "service-atomic"
    ]
    return [
        {
            "rows": len(rows),
            "unique_keys": len(
                {(row["schedule"], row["policy"], row["scenario_id"]) for row in rows}
            ),
            "attack_rows": len(attacks),
            "control_rows": len(controls),
            "stale_commits": sum(int(row["attack"]) for row in attacks),
            "control_tasks": sum(int(row["task"]) for row in controls),
            "critical_atomic_rows": len(critical_atomic_attacks),
            "critical_verifier_gates": sum(
                int(row["verifier_gate"]) for row in critical_atomic_attacks
            ),
            "critical_mutation_request_gates": sum(
                int(row["mutation_requested_after_verify"])
                for row in critical_atomic_attacks
            ),
            "critical_deferred_lock_gates": sum(
                int(row["mutation_deferred_at_gate"])
                for row in critical_atomic_attacks
            ),
            "critical_serialized_commits": sum(
                int(row["serialized_commit_before_mutation"])
                for row in critical_atomic_attacks
            ),
            "duplicate_rows": sum(int(row["duplicate_delivery"]) for row in rows),
            "delivery_attempts": sum(int(row["delivery_attempts"]) for row in rows),
            "effect_rows": sum(int(row["effect_rows"]) for row in rows),
            "nonce_rows": sum(int(row["nonce_rows"]) for row in rows),
            "distinct_service_role_rows": sum(int(row["role_distinct"]) for row in rows),
        }
    ]


def validate(rows: list[dict[str, Any]], scenarios: list[dict[str, Any]]) -> None:
    by_schedule = {
        "pre-transaction": scenarios,
        "critical-window": [
            scenario for scenario in scenarios if scenario["family"] in CRITICAL_FAMILIES
        ],
    }
    expected = {
        (schedule, policy, str(scenario["id"]))
        for schedule, selected in by_schedule.items()
        for policy in POLICIES
        for scenario in selected
    }
    observed = {
        (str(row["schedule"]), str(row["policy"]), str(row["scenario_id"]))
        for row in rows
    }
    if len(rows) != 540 or observed != expected:
        raise ValueError("service-integrated matrix is incomplete or duplicated")
    for row in rows:
        is_attack = row["scenario_type"] == "attack"
        is_atomic = row["policy"] == "service-atomic"
        is_critical = row["schedule"] == "critical-window"
        expected_effect = not (is_atomic and not is_critical and is_attack)
        expected_stale = is_attack and not is_atomic
        expected_attempts = 2 if row["duplicate_delivery"] else 1
        expected_nonce = int(
            is_atomic
            and expected_effect
            and row["family"] == "confirmation-replay"
        )
        if (
            int(row["committed"]) != int(expected_effect)
            or int(row["effect_rows"]) != int(expected_effect)
            or int(row["attack"]) != int(expected_stale)
            or int(row["task"]) != int(not is_attack and expected_effect)
            or int(row["delivery_attempts"]) != expected_attempts
            or int(row["nonce_rows"]) != expected_nonce
            or int(row["external_verify_allow"]) != 1
            or int(row["role_distinct"]) != 1
        ):
            raise ValueError(f"service-integrated outcome mismatch: {row}")
        if row["duplicate_delivery"] and expected_effect and not row["second_idempotent"]:
            raise ValueError(f"allowed duplicate was not idempotent: {row}")
        if row["duplicate_delivery"] and not expected_effect and row["second_idempotent"]:
            raise ValueError(f"blocked duplicate was marked idempotent: {row}")
        if is_attack and not is_critical and not row["mutation_applied_before_request"]:
            raise ValueError(f"pre-transaction mutation gate failed: {row}")
        if is_attack and is_critical and not is_atomic:
            if not row["mutation_applied_before_request"]:
                raise ValueError(f"split critical-window mutation gate failed: {row}")
        if is_attack and is_critical and is_atomic:
            if not (
                row["verifier_gate"]
                and row["mutation_requested_after_verify"]
                and row["mutation_deferred_at_gate"]
                and row["serialized_commit_before_mutation"]
                and row["authorized_attack_commit"]
            ):
                raise ValueError(f"atomic critical-window gate failed: {row}")
    totals = integrity(rows)[0]
    frozen = {
        "rows": 540,
        "unique_keys": 540,
        "attack_rows": 360,
        "control_rows": 180,
        "stale_commits": 180,
        "control_tasks": 180,
        "critical_atomic_rows": 80,
        "critical_verifier_gates": 80,
        "critical_mutation_request_gates": 80,
        "critical_deferred_lock_gates": 80,
        "critical_serialized_commits": 80,
        "duplicate_rows": 108,
        "delivery_attempts": 648,
        "effect_rows": 440,
        "nonce_rows": 40,
        "distinct_service_role_rows": 540,
    }
    if totals != frozen:
        raise ValueError(f"service-integrated frozen totals mismatch: {totals}")


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario-dir",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "commit-race-heldout",
    )
    parser.add_argument(
        "--analysis-prefix",
        type=pathlib.Path,
        default=ROOT / "analysis" / "service_integrated_commit",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    output_paths = [
        pathlib.Path(f"{args.analysis_prefix}_detail.csv"),
        pathlib.Path(f"{args.analysis_prefix}_summary.csv"),
        pathlib.Path(f"{args.analysis_prefix}_integrity.csv"),
    ]
    if any(path.exists() for path in output_paths) and not args.overwrite:
        raise SystemExit("output exists; pass --overwrite for one fresh complete matrix")
    scenarios = load_scenarios(args.scenario_dir)
    key = secrets.token_bytes(32)
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="psebench-service-integrated-") as directory:
        for schedule in SCHEDULES:
            selected = (
                scenarios
                if schedule == "pre-transaction"
                else [
                    scenario
                    for scenario in scenarios
                    if scenario["family"] in CRITICAL_FAMILIES
                ]
            )
            for policy in POLICIES:
                database_path = pathlib.Path(directory) / f"{schedule}-{policy}.sqlite"
                with IntegratedServiceProcess(database_path, key) as service:
                    for scenario in selected:
                        rows.append(run_case(service, key, scenario, policy, schedule))
        validate(rows, scenarios)
    write_csv(output_paths[0], rows)
    write_csv(output_paths[1], summarize(rows))
    write_csv(output_paths[2], integrity(rows))
    print(
        "service-integrated commit matrix passed: rows=540 attacks=360 "
        "controls=180 stale_split=180 stale_atomic=0 serialized_windows=80"
    )


if __name__ == "__main__":
    main()
