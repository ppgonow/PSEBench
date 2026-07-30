#!/usr/bin/env python3
"""Run check-to-commit invalidations across three HTTP service processes."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from dataclasses import dataclass, field
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import multiprocessing
import os
import pathlib
import queue
import secrets
import sqlite3
import statistics
import sys
import threading
import time
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from commit_binding import (  # noqa: E402
    CheckContext,
    CommitContext,
    CommitReceipt,
    issue_receipt,
    verify_commit,
)
from effect_boundary import EffectSpec  # noqa: E402
from run_http_commit_race import (  # noqa: E402
    EXPECTED_FAMILIES,
    exact_mcnemar,
    load_scenarios,
    wilson,
)


POLICIES = (
    "check-once",
    "PAuth-style/pre-action",
    "PCAS-style/pre-action",
    "receipt-bound",
)
STALE_POLICIES = set(POLICIES) - {"receipt-bound"}


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[rank]


def post_json(base_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    request = Request(
        base_url + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        result = json.loads(response.read())
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


class PersistentJsonPool:
    """Bounded HTTP/1.1 pool for loopback load measurements."""

    def __init__(self, base_url: str, size: int, *, timeout: float = 20.0):
        if size < 1:
            raise ValueError("pool size must be positive")
        parsed = urlsplit(base_url)
        if parsed.scheme != "http" or not parsed.hostname or parsed.path not in ("", "/"):
            raise ValueError(f"unsupported pooled HTTP base URL: {base_url}")
        self.host = parsed.hostname
        self.port = parsed.port or 80
        self.timeout = timeout
        self.connections: queue.LifoQueue[http.client.HTTPConnection] = queue.LifoQueue(
            maxsize=size
        )
        created: list[http.client.HTTPConnection] = []
        try:
            for _ in range(size):
                connection = self._new_connection(connect=True)
                created.append(connection)
                self.connections.put_nowait(connection)
        except Exception:
            for connection in created:
                connection.close()
            raise

    def _new_connection(self, *, connect: bool) -> http.client.HTTPConnection:
        connection = http.client.HTTPConnection(
            self.host, self.port, timeout=self.timeout
        )
        if connect:
            connection.connect()
        return connection

    def _replace(self, connection: http.client.HTTPConnection) -> None:
        connection.close()
        replacement = self._new_connection(connect=False)
        self.connections.put(replacement)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not path.startswith("/"):
            raise ValueError("pooled request path must start with '/'")
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        connection = self.connections.get(timeout=self.timeout)
        try:
            connection.request(
                "POST",
                path,
                body=body,
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                },
            )
            response = connection.getresponse()
            response_body = response.read()
            status = response.status
            reusable = not response.will_close
        except Exception:
            self._replace(connection)
            raise
        if reusable:
            self.connections.put(connection)
        else:
            self._replace(connection)
        result = json.loads(response_body)
        if status != 200 or "error" in result:
            raise RuntimeError(result.get("error", f"HTTP status {status}"))
        return result

    def close(self) -> None:
        while True:
            try:
                self.connections.get_nowait().close()
            except queue.Empty:
                break

    def __enter__(self) -> "PersistentJsonPool":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def receipt_from_dict(payload: dict[str, Any]) -> CommitReceipt:
    return CommitReceipt(
        principal=str(payload["principal"]),
        authorization_version=int(payload["authorization_version"]),
        checked_effect=EffectSpec(**payload["checked_effect"]),
        checked_at=int(payload["checked_at"]),
        expires_at=int(payload["expires_at"]),
        confirmation_nonce=payload.get("confirmation_nonce"),
        authentication_tag=str(payload["authentication_tag"]),
    )


@dataclass
class AuthorizationTrial:
    receipt: CommitReceipt
    current_effect: EffectSpec
    current_context: CommitContext
    lock: threading.Lock = field(default_factory=threading.Lock)
    mutation_request_received_ns: int | None = None
    mutation_applied_ns: int | None = None
    mutation_completed_ns: int | None = None


class AuthorizationService:
    def __init__(self, authentication_key: bytes, state_delay_ms: float):
        self.authentication_key = authentication_key
        self.state_delay_ms = state_delay_ms
        self.trials: dict[str, AuthorizationTrial] = {}
        self.trials_lock = threading.Lock()

    def _trial(self, trial_id: str) -> AuthorizationTrial:
        with self.trials_lock:
            try:
                return self.trials[trial_id]
            except KeyError as exc:
                raise ValueError(f"unknown trial: {trial_id}") from exc

    def dispatch(
        self, path: str, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        if path == "/health":
            return {"role": "authorization", "pid": os.getpid()}
        if path == "/check":
            return self.check(payload)
        if path == "/mutate":
            return self.mutate(payload, request_received_ns)
        if path == "/mutation-status":
            return self.mutation_status(payload)
        if path == "/state":
            return self.state(payload, request_received_ns)
        raise ValueError(f"unknown authorization route: {path}")

    def check(self, payload: dict[str, Any]) -> dict[str, Any]:
        trial_id = str(payload["trial_id"])
        policy = str(payload["policy"])
        if policy not in POLICIES:
            raise ValueError(f"unknown policy: {policy}")
        authorized = EffectSpec(**payload["authorized_effect"])
        checked = EffectSpec(**payload["checked_effect"])
        context = CheckContext(**payload["check_context"])
        receipt = issue_receipt(
            authorized, checked, context, self.authentication_key
        )
        committed_at = min(context.expires_at, context.checked_at + 1)
        current_context = CommitContext(
            principal=context.principal,
            authorization_version=context.authorization_version,
            committed_at=committed_at,
            confirmation_nonce=context.confirmation_nonce,
            nonce_consumed=False,
        )
        trial = AuthorizationTrial(receipt, checked, current_context)
        with self.trials_lock:
            if trial_id in self.trials:
                raise ValueError(f"duplicate trial: {trial_id}")
            self.trials[trial_id] = trial
        return {
            "trial_id": trial_id,
            "decision": "allow",
            "receipt": receipt.to_dict(),
            "service_pid": os.getpid(),
            "checked_ns": time.perf_counter_ns(),
        }

    def mutate(
        self, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        trial = self._trial(str(payload["trial_id"]))
        hold_ms = float(payload.get("hold_ms", 0.0))
        if hold_ms < 0 or hold_ms > 1000:
            raise ValueError("hold_ms must be between 0 and 1000")
        with trial.lock:
            trial.mutation_request_received_ns = request_received_ns
            trial.current_effect = EffectSpec(**payload["commit_effect"])
            trial.current_context = CommitContext(**payload["commit_context"])
            trial.mutation_applied_ns = time.perf_counter_ns()
            time.sleep(hold_ms / 1000.0)
            trial.mutation_completed_ns = time.perf_counter_ns()
            return {
                "service_pid": os.getpid(),
                "mutation_request_received_ns": trial.mutation_request_received_ns,
                "mutation_applied_ns": trial.mutation_applied_ns,
                "mutation_completed_ns": trial.mutation_completed_ns,
            }

    def mutation_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        trial = self._trial(str(payload["trial_id"]))
        return {
            "service_pid": os.getpid(),
            "mutation_applied_ns": trial.mutation_applied_ns,
            "mutation_completed_ns": trial.mutation_completed_ns,
        }

    def state(
        self, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        trial = self._trial(str(payload["trial_id"]))
        with trial.lock:
            serialized_ns = time.perf_counter_ns()
            time.sleep(self.state_delay_ms / 1000.0)
            return {
                "service_pid": os.getpid(),
                "effect": trial.current_effect.to_dict(),
                "context": {
                    "principal": trial.current_context.principal,
                    "authorization_version": trial.current_context.authorization_version,
                    "committed_at": trial.current_context.committed_at,
                    "confirmation_nonce": trial.current_context.confirmation_nonce,
                    "nonce_consumed": trial.current_context.nonce_consumed,
                },
                "state_request_received_ns": request_received_ns,
                "state_serialized_ns": serialized_ns,
                "mutation_request_received_ns": trial.mutation_request_received_ns,
                "mutation_applied_ns": trial.mutation_applied_ns,
                "mutation_completed_ns": trial.mutation_completed_ns,
            }


class EffectService:
    def __init__(self, database_path: pathlib.Path, service_delay_ms: float):
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.service_delay_ms = service_delay_ms
        self.lock = threading.RLock()
        self.database = sqlite3.connect(database_path, check_same_thread=False)
        self.database.execute(
            """
            CREATE TABLE commits (
                trial_id TEXT PRIMARY KEY,
                policy TEXT NOT NULL,
                effect_json TEXT NOT NULL,
                committed_ns INTEGER NOT NULL
            )
            """
        )
        self.database.execute(
            """
            CREATE TABLE delivery_attempts (
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                trial_id TEXT NOT NULL,
                received_ns INTEGER NOT NULL
            )
            """
        )
        self.database.commit()

    def close(self) -> None:
        self.database.close()

    def dispatch(
        self, path: str, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        if path == "/health":
            return {"role": "effect", "pid": os.getpid()}
        if path == "/commit":
            return self.commit(payload, request_received_ns)
        if path == "/count":
            return self.count(str(payload["trial_id"]))
        raise ValueError(f"unknown effect route: {path}")

    def commit(
        self, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        trial_id = str(payload["trial_id"])
        with self.lock:
            self.database.execute(
                "INSERT INTO delivery_attempts (trial_id, received_ns) VALUES (?, ?)",
                (trial_id, request_received_ns),
            )
            self.database.execute(
                "INSERT OR IGNORE INTO commits VALUES (?, ?, ?, ?)",
                (
                    trial_id,
                    str(payload["policy"]),
                    json.dumps(payload["effect"], sort_keys=True),
                    time.perf_counter_ns(),
                ),
            )
            self.database.commit()
            time.sleep(self.service_delay_ms / 1000.0)
            counts = self.count(trial_id)
        return {"service_pid": os.getpid(), **counts}

    def count(self, trial_id: str) -> dict[str, Any]:
        with self.lock:
            commit_rows = self.database.execute(
                "SELECT COUNT(*) FROM commits WHERE trial_id = ?", (trial_id,)
            ).fetchone()[0]
            attempt_rows = self.database.execute(
                "SELECT COUNT(*) FROM delivery_attempts WHERE trial_id = ?", (trial_id,)
            ).fetchone()[0]
        return {
            "service_pid": os.getpid(),
            "ledger_rows": int(commit_rows),
            "delivery_attempts": int(attempt_rows),
        }


class CommitGateway:
    def __init__(
        self,
        authorization_url: str,
        effect_url: str,
        authentication_key: bytes,
        *,
        pooled_http: bool = False,
        pool_size: int = 32,
    ):
        self.authorization_url = authorization_url
        self.effect_url = effect_url
        self.authentication_key = authentication_key
        self.authorization_pool = (
            PersistentJsonPool(authorization_url, pool_size) if pooled_http else None
        )
        self.effect_pool = PersistentJsonPool(effect_url, pool_size) if pooled_http else None

    def _post(
        self,
        service: str,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if service == "authorization":
            pool = self.authorization_pool
            url = self.authorization_url
        elif service == "effect":
            pool = self.effect_pool
            url = self.effect_url
        else:  # pragma: no cover - internal programming error
            raise ValueError(f"unknown gateway service: {service}")
        return pool.post(path, payload) if pool is not None else post_json(url, path, payload)

    def close(self) -> None:
        if self.authorization_pool is not None:
            self.authorization_pool.close()
        if self.effect_pool is not None:
            self.effect_pool.close()

    def dispatch(
        self, path: str, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        if path == "/health":
            return {"role": "gateway", "pid": os.getpid()}
        if path == "/commit":
            return self.commit(payload, request_received_ns)
        raise ValueError(f"unknown gateway route: {path}")

    def commit(
        self, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        started_ns = time.perf_counter_ns()
        trial_id = str(payload["trial_id"])
        policy = str(payload["policy"])
        if policy not in POLICIES:
            raise ValueError(f"unknown policy: {policy}")
        commit_effect = EffectSpec(**payload["commit_effect"])
        auth_query_us = 0.0
        state_response: dict[str, Any] | None = None
        binding_decision = "not_evaluated"
        binding_reason = "pre-action decision is not revalidated at commit"

        if policy == "receipt-bound":
            auth_started_ns = time.perf_counter_ns()
            state_response = self._post(
                "authorization", "/state", {"trial_id": trial_id}
            )
            auth_query_us = (time.perf_counter_ns() - auth_started_ns) / 1000.0
            receipt = receipt_from_dict(payload["receipt"])
            current_effect = EffectSpec(**state_response["effect"])
            current_context = CommitContext(**state_response["context"])
            bound = verify_commit(
                receipt,
                current_effect,
                current_context,
                self.authentication_key,
            )
            binding_decision = bound.decision
            binding_reason = bound.reason
            decision = bound.decision
            effect_for_service = current_effect
        else:
            decision = "allow"
            effect_for_service = commit_effect

        service_call_us = 0.0
        delivery_attempts = 0
        ledger_rows = 0
        effect_pid: int | None = None
        if decision == "allow":
            attempts = 2 if bool(payload.get("duplicate_delivery")) else 1
            service_started_ns = time.perf_counter_ns()
            service_response: dict[str, Any] | None = None
            for _ in range(attempts):
                service_response = self._post(
                    "effect",
                    "/commit",
                    {
                        "trial_id": trial_id,
                        "policy": policy,
                        "effect": effect_for_service.to_dict(),
                    },
                )
            service_call_us = (time.perf_counter_ns() - service_started_ns) / 1000.0
            assert service_response is not None
            delivery_attempts = int(service_response["delivery_attempts"])
            ledger_rows = int(service_response["ledger_rows"])
            effect_pid = int(service_response["service_pid"])
        else:
            count = self._post("effect", "/count", {"trial_id": trial_id})
            delivery_attempts = int(count["delivery_attempts"])
            ledger_rows = int(count["ledger_rows"])
            effect_pid = int(count["service_pid"])

        decided_ns = time.perf_counter_ns()
        return {
            "gateway_pid": os.getpid(),
            "effect_pid": effect_pid,
            "decision": decision,
            "reason": (
                "cached check-time allow without commit revalidation"
                if policy in STALE_POLICIES
                else binding_reason
            ),
            "binding_decision": binding_decision,
            "binding_reason": binding_reason,
            "committed": decision == "allow",
            "ledger_rows": ledger_rows,
            "delivery_attempts": delivery_attempts,
            "auth_query_us": round(auth_query_us, 3),
            "service_call_us": round(service_call_us, 3),
            "gateway_total_us": round((decided_ns - started_ns) / 1000.0, 3),
            "commit_request_received_ns": request_received_ns,
            "gateway_decided_ns": decided_ns,
            "state_response": state_response,
        }


class JsonHandler(BaseHTTPRequestHandler):
    server: "JsonHTTPServer"
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:  # noqa: N802
        received_ns = time.perf_counter_ns()
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 1024 * 1024:
                raise ValueError("invalid JSON body length")
            payload = json.loads(self.rfile.read(length))
            result = self.server.app.dispatch(self.path, payload, received_ns)
            body = json.dumps(result, sort_keys=True).encode("utf-8")
            self.send_response(200)
        except Exception as exc:  # pragma: no cover - CLI failure path
            body = json.dumps({"error": str(exc)}, sort_keys=True).encode("utf-8")
            self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class JsonHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], app: Any):
        super().__init__(address, JsonHandler)
        self.app = app


def serve_process(
    role: str,
    connection: Any,
    stop_event: Any,
    config: dict[str, Any],
) -> None:
    app: Any
    if role == "authorization":
        app = AuthorizationService(
            config["authentication_key"], config["state_delay_ms"]
        )
    elif role == "effect":
        app = EffectService(
            pathlib.Path(config["database_path"]), config["service_delay_ms"]
        )
    elif role == "gateway":
        app = CommitGateway(
            config["authorization_url"],
            config["effect_url"],
            config["authentication_key"],
            pooled_http=bool(config.get("pooled_http", False)),
            pool_size=int(config.get("pool_size", 32)),
        )
    else:  # pragma: no cover - internal programming error
        raise ValueError(f"unknown service role: {role}")
    server = JsonHTTPServer(("127.0.0.1", 0), app)
    server.timeout = 0.2
    connection.send({"port": server.server_port, "pid": os.getpid()})
    connection.close()
    try:
        while not stop_event.is_set():
            server.handle_request()
    finally:
        server.server_close()
        close = getattr(app, "close", None)
        if close is not None:
            close()


class ServiceCluster:
    def __init__(
        self,
        database_path: pathlib.Path,
        authentication_key: bytes,
        *,
        state_delay_ms: float,
        service_delay_ms: float,
        pooled_http: bool = False,
        pool_size: int = 32,
    ):
        self.database_path = database_path
        self.authentication_key = authentication_key
        self.state_delay_ms = state_delay_ms
        self.service_delay_ms = service_delay_ms
        self.pooled_http = pooled_http
        self.pool_size = pool_size
        self.processes: list[multiprocessing.Process] = []
        self.events: list[Any] = []
        self.urls: dict[str, str] = {}
        self.pids: dict[str, int] = {}

    def _start(self, role: str, config: dict[str, Any]) -> str:
        parent, child = multiprocessing.Pipe(duplex=False)
        stop_event = multiprocessing.Event()
        process = multiprocessing.Process(
            target=serve_process,
            args=(role, child, stop_event, config),
            name=f"psebench-{role}",
        )
        process.start()
        child.close()
        if not parent.poll(10):
            process.terminate()
            process.join(timeout=5)
            raise RuntimeError(f"{role} service did not start")
        ready = parent.recv()
        parent.close()
        self.processes.append(process)
        self.events.append(stop_event)
        url = f"http://127.0.0.1:{ready['port']}"
        self.urls[role] = url
        self.pids[role] = int(ready["pid"])
        health = post_json(url, "/health", {})
        if health["role"] != role or int(health["pid"]) != self.pids[role]:
            raise RuntimeError(f"{role} health identity mismatch")
        return url

    def start(self) -> "ServiceCluster":
        authorization_url = self._start(
            "authorization",
            {
                "authentication_key": self.authentication_key,
                "state_delay_ms": self.state_delay_ms,
            },
        )
        effect_url = self._start(
            "effect",
            {
                "database_path": str(self.database_path),
                "service_delay_ms": self.service_delay_ms,
            },
        )
        self._start(
            "gateway",
            {
                "authorization_url": authorization_url,
                "effect_url": effect_url,
                "authentication_key": self.authentication_key,
                "pooled_http": self.pooled_http,
                "pool_size": self.pool_size,
            },
        )
        if len(set(self.pids.values())) != 3 or os.getpid() in self.pids.values():
            raise RuntimeError(f"services are not distinct child processes: {self.pids}")
        return self

    def close(self) -> None:
        for event in self.events:
            event.set()
        for role, url in self.urls.items():
            try:
                post_json(url, "/health", {})
            except Exception:
                pass
        for process in self.processes:
            process.join(timeout=5)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        failed = [process.exitcode for process in self.processes if process.exitcode]
        if failed:
            raise RuntimeError(f"service processes exited unsuccessfully: {failed}")

    def __enter__(self) -> "ServiceCluster":
        return self.start()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def duplicate_delivery_for(scenario_id: str) -> bool:
    digits = "".join(character for character in scenario_id if character.isdigit())
    return bool(digits) and int(digits[-3:]) % 5 == 0


def run_one(
    cluster: ServiceCluster,
    policy: str,
    scenario: dict[str, Any],
    *,
    commit_delay_ms: float,
    mutation_hold_ms: float,
) -> dict[str, Any]:
    scenario_id = str(scenario["id"])
    trial_id = f"{policy}:{scenario_id}"
    race = scenario["commit_race"]
    checked = post_json(
        cluster.urls["authorization"],
        "/check",
        {
            "trial_id": trial_id,
            "policy": policy,
            "authorized_effect": race["authorized_effect"],
            "checked_effect": race["checked_effect"],
            "check_context": race["check_context"],
        },
    )
    duplicate_delivery = duplicate_delivery_for(scenario_id)
    commit_payload = {
        "trial_id": trial_id,
        "policy": policy,
        "receipt": checked["receipt"],
        "commit_effect": race["commit_effect"],
        "duplicate_delivery": duplicate_delivery,
    }
    mutation_response: dict[str, Any] | None = None
    if scenario["type"] == "attack":
        barrier = threading.Barrier(3)
        responses: dict[str, dict[str, Any]] = {}
        errors: list[BaseException] = []

        def mutate_worker() -> None:
            try:
                barrier.wait()
                responses["mutation"] = post_json(
                    cluster.urls["authorization"],
                    "/mutate",
                    {
                        "trial_id": trial_id,
                        "commit_effect": race["commit_effect"],
                        "commit_context": race["commit_context"],
                        "hold_ms": mutation_hold_ms,
                    },
                )
            except BaseException as error:
                errors.append(error)

        def commit_worker() -> None:
            try:
                barrier.wait()
                deadline = time.monotonic() + 10
                while True:
                    status = post_json(
                        cluster.urls["authorization"],
                        "/mutation-status",
                        {"trial_id": trial_id},
                    )
                    if status["mutation_applied_ns"] is not None:
                        break
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            f"mutation was not applied before commit for {trial_id}"
                        )
                    time.sleep(0.0005)
                time.sleep(commit_delay_ms / 1000.0)
                precommit_status = post_json(
                    cluster.urls["authorization"],
                    "/mutation-status",
                    {"trial_id": trial_id},
                )
                if (
                    precommit_status["mutation_applied_ns"] is None
                    or precommit_status["mutation_completed_ns"] is not None
                ):
                    raise RuntimeError(
                        f"mutation was not active immediately before commit for {trial_id}"
                    )
                responses["precommit_status"] = precommit_status
                responses["commit"] = post_json(
                    cluster.urls["gateway"], "/commit", commit_payload
                )
            except BaseException as error:
                errors.append(error)

        workers = [
            threading.Thread(target=mutate_worker),
            threading.Thread(target=commit_worker),
        ]
        for worker in workers:
            worker.start()
        barrier.wait()
        for worker in workers:
            worker.join()
        if errors:
            raise RuntimeError(f"concurrent request failed for {trial_id}: {errors}")
        mutation_response = responses["mutation"]
        precommit_status = responses["precommit_status"]
        commit_response = responses["commit"]
    else:
        commit_response = post_json(
            cluster.urls["gateway"], "/commit", commit_payload
        )

    state = post_json(
        cluster.urls["authorization"], "/state", {"trial_id": trial_id}
    )
    committed = bool(commit_response["committed"])
    valid_at_commit = bool(race["expected_valid_at_commit"])
    mutation_before_commit = False
    request_overlap = False
    if scenario["type"] == "attack":
        assert mutation_response is not None
        mutation_before_commit = precommit_status["mutation_applied_ns"] is not None
        request_overlap = precommit_status["mutation_completed_ns"] is None
    return {
        "scenario_id": scenario_id,
        "family": scenario["family"],
        "scenario_type": scenario["type"],
        "policy": policy,
        "invalidation": race["pre_registered_invalidation"],
        "attack": int(committed and not valid_at_commit),
        "task": int(committed and valid_at_commit),
        "committed": int(committed),
        "valid_at_commit": int(valid_at_commit),
        "duplicate_delivery": int(duplicate_delivery),
        "delivery_attempts": int(commit_response["delivery_attempts"]),
        "ledger_rows": int(commit_response["ledger_rows"]),
        "mutation_before_commit": int(mutation_before_commit),
        "request_overlap": int(request_overlap),
        "precommit_mutation_active": int(
            mutation_before_commit and request_overlap
        ),
        "authorization_pid": int(checked["service_pid"]),
        "gateway_pid": int(commit_response["gateway_pid"]),
        "effect_pid": int(commit_response["effect_pid"]),
        "policy_decision": commit_response["decision"],
        "binding_decision": commit_response["binding_decision"],
        "auth_query_us": float(commit_response["auth_query_us"]),
        "service_call_us": float(commit_response["service_call_us"]),
        "gateway_total_us": float(commit_response["gateway_total_us"]),
        "state_effect_json": json.dumps(state["effect"], sort_keys=True),
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[("overall", "all", row["policy"])].append(row)
        groups[("family", row["family"], row["policy"])].append(row)
    output = []
    for (scope, family, policy), items in sorted(groups.items()):
        attacks = [item for item in items if item["scenario_type"] == "attack"]
        controls = [item for item in items if item["scenario_type"] == "benign"]
        attack_yes = sum(item["attack"] for item in attacks)
        task_yes = sum(item["task"] for item in controls)
        attack_ci = wilson(attack_yes, len(attacks))
        task_ci = wilson(task_yes, len(controls))
        control_latencies = [item["gateway_total_us"] for item in controls]
        output.append(
            {
                "scope": scope,
                "family": family,
                "policy": policy,
                "attack_n": len(attacks),
                "attack_yes": attack_yes,
                "ASR": round(attack_yes / len(attacks), 6),
                "ASR_CI_low": round(attack_ci[0], 6),
                "ASR_CI_high": round(attack_ci[1], 6),
                "benign_n": len(controls),
                "task_yes": task_yes,
                "TCR": round(task_yes / len(controls), 6),
                "TCR_CI_low": round(task_ci[0], 6),
                "TCR_CI_high": round(task_ci[1], 6),
                "attack_mutation_before_commit": sum(
                    item["mutation_before_commit"] for item in attacks
                ),
                "attack_request_overlap": sum(
                    item["request_overlap"] for item in attacks
                ),
                "retry_rows": sum(item["delivery_attempts"] == 2 for item in items),
                "ledger_rows": sum(item["ledger_rows"] for item in items),
                "control_gateway_median_us": round(
                    statistics.median(control_latencies), 3
                ),
                "control_gateway_p95_us": round(
                    percentile(control_latencies, 0.95), 3
                ),
            }
        )
    return output


def paired(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {(row["policy"], row["scenario_id"]): row for row in rows}
    attack_rows = [row for row in rows if row["scenario_type"] == "attack"]
    output = []
    for comparator in POLICIES[:-1]:
        for family in ["all", *sorted(EXPECTED_FAMILIES)]:
            ids = sorted(
                {
                    row["scenario_id"]
                    for row in attack_rows
                    if family == "all" or row["family"] == family
                }
            )
            b = sum(
                indexed[(comparator, item)]["attack"]
                and not indexed[("receipt-bound", item)]["attack"]
                for item in ids
            )
            c = sum(
                not indexed[(comparator, item)]["attack"]
                and indexed[("receipt-bound", item)]["attack"]
                for item in ids
            )
            output.append(
                {
                    "comparator": comparator,
                    "family": family,
                    "n_pairs": len(ids),
                    "comparator_yes_receipt_no": b,
                    "comparator_no_receipt_yes": c,
                    "exact_mcnemar_p": exact_mcnemar(b, c),
                }
            )
    return output


def validate_complete(
    rows: list[dict[str, Any]], scenarios: list[dict[str, Any]], pids: dict[str, int]
) -> None:
    expected_ids = {str(item["id"]) for item in scenarios}
    expected_keys = {(policy, scenario_id) for policy in POLICIES for scenario_id in expected_ids}
    actual_keys = {(row["policy"], row["scenario_id"]) for row in rows}
    if len(rows) != 600 or actual_keys != expected_keys:
        raise ValueError(
            f"incomplete matrix: rows={len(rows)}, missing={sorted(expected_keys - actual_keys)[:5]}"
        )
    expected_pid_set = set(pids.values())
    for row in rows:
        if {
            row["authorization_pid"],
            row["gateway_pid"],
            row["effect_pid"],
        } != expected_pid_set:
            raise ValueError(f"service PID mismatch for {row['policy']}/{row['scenario_id']}")
        expected_ledger = 1 if row["committed"] else 0
        expected_attempts = (
            2 if row["committed"] and row["duplicate_delivery"] else expected_ledger
        )
        if row["ledger_rows"] != expected_ledger:
            raise ValueError(f"ledger mismatch for {row['policy']}/{row['scenario_id']}")
        if row["delivery_attempts"] != expected_attempts:
            raise ValueError(f"delivery attempt mismatch for {row['policy']}/{row['scenario_id']}")
        if row["scenario_type"] == "attack":
            if not row["mutation_before_commit"] or not row["request_overlap"]:
                raise ValueError(
                    f"failed timing manipulation for {row['policy']}/{row['scenario_id']}"
                )


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
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
        "--output-root",
        type=pathlib.Path,
        default=ROOT / "results" / "multiprocess_commit_race",
    )
    parser.add_argument(
        "--analysis-prefix",
        type=pathlib.Path,
        default=ROOT / "analysis" / "multiprocess_commit_race",
    )
    parser.add_argument("--commit-delay-ms", type=float, default=2.0)
    parser.add_argument("--mutation-hold-ms", type=float, default=8.0)
    parser.add_argument("--state-delay-ms", type=float, default=0.5)
    parser.add_argument("--service-delay-ms", type=float, default=0.5)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.commit_delay_ms < 0 or args.mutation_hold_ms <= args.commit_delay_ms:
        raise SystemExit("mutation hold must be positive and exceed commit delay")
    if args.state_delay_ms < 0 or args.service_delay_ms < 0:
        raise SystemExit("service delays must be non-negative")

    scenarios = load_scenarios(args.scenario_dir)
    raw_path = args.output_root / "multiprocess_commit_race.jsonl"
    database_path = args.output_root / "service.sqlite"
    if (raw_path.exists() or database_path.exists()) and not args.overwrite:
        raise SystemExit("output exists; pass --overwrite for a fresh complete matrix")
    args.output_root.mkdir(parents=True, exist_ok=True)
    if raw_path.exists():
        raw_path.unlink()
    if database_path.exists():
        database_path.unlink()

    key = secrets.token_bytes(32)
    rows: list[dict[str, Any]] = []
    with ServiceCluster(
        database_path,
        key,
        state_delay_ms=args.state_delay_ms,
        service_delay_ms=args.service_delay_ms,
    ) as cluster:
        for policy in POLICIES:
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
        validate_complete(rows, scenarios, cluster.pids)

    raw_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    write_csv(pathlib.Path(f"{args.analysis_prefix}_detail.csv"), rows)
    write_csv(pathlib.Path(f"{args.analysis_prefix}_summary.csv"), summarize(rows))
    write_csv(pathlib.Path(f"{args.analysis_prefix}_paired.csv"), paired(rows))
    print(
        "completed 600 three-process HTTP policy/scenario observations; "
        "timing, retry, PID, and SQLite ledger checks passed"
    )


if __name__ == "__main__":
    main()
