#!/usr/bin/env python3
"""Replay frozen native proposals through a three-process commit chain."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import json
import multiprocessing
import os
import pathlib
import secrets
import sqlite3
import statistics
import sys
import tempfile
import threading
import time
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
from commit_binding import CheckContext, CommitContext, issue_receipt  # noqa: E402
from effect_boundary import EffectSpec, check_effect  # noqa: E402
from run_http_commit_race import exact_mcnemar, wilson  # noqa: E402
from run_multiprocess_commit_race import JsonHTTPServer, percentile, post_json  # noqa: E402
from run_same_tool_native_commit import load_scenarios  # noqa: E402
from same_tool_effects import authorized_effect  # noqa: E402
from service_integrated_commit import ServiceIntegratedEffect  # noqa: E402


ALIASES = ("gpt-5.5", "grok-4.5", "gpt-5.4", "gpt-5.6-sol")
POLICIES = ("cached-pre-action", "receipt-bound")
STATES = ("stable", "revoked")
RUN_ID = "native-service-bridge-20260721-v1"
MUTATION_HOLD_MS = 1000.0
COMMIT_DELAY_MS = 10.0
EXPECTED_INPUT_HASHES = {
    "gpt-5.5": "58b5215d63b978ddd4314aa07fa843cce581bcf3f501625a33fa4babd1b77a5b",
    "grok-4.5": "7e47db5b520deef844fdd89f6742913867f113cd346217c4554b08f98fa66380",
    "gpt-5.4": "205a6e2029f9e1250ff9c3c4780fd01167487c40622d709b378e6c828708e717",
    "gpt-5.6-sol": "330067db82a8c949e5c35e48cb83e9d2e47c6d2208343c1f4af601fb85eebd38",
}
INPUT_FILENAMES = {
    "gpt-5.5": "same_tool_native_commit_gpt_5_5_final.jsonl",
    "grok-4.5": "same_tool_native_commit_grok_4_5_final.jsonl",
    "gpt-5.4": "same_tool_native_commit_gpt_5_4_final.jsonl",
    "gpt-5.6-sol": "same_tool_native_commit_gpt_5_6_sol_final.jsonl",
}
EXPECTED_MANIFEST_HASH = "bb113d09247bb37beb0f03e44e1594e487d5414d399a445d3f33f95fed52bb43"


def file_sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def value_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def append_jsonl(path: pathlib.Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def write_jsonl(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        temporary = pathlib.Path(handle.name)
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    os.replace(temporary, path)


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def input_path(alias: str, input_root: pathlib.Path) -> pathlib.Path:
    return input_root / INPUT_FILENAMES[alias]


def load_frozen_proposals(
    input_root: pathlib.Path, manifest: pathlib.Path
) -> list[dict[str, Any]]:
    if file_sha256(manifest) != EXPECTED_MANIFEST_HASH:
        raise ValueError("same-tool manifest differs from the pre-registered input")
    scenarios = {item["id"]: item for item in load_scenarios(manifest)}
    proposals: list[dict[str, Any]] = []
    for alias in ALIASES:
        path = input_path(alias, input_root)
        if file_sha256(path) != EXPECTED_INPUT_HASHES[alias]:
            raise ValueError(f"native input hash mismatch for {alias}")
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if len(rows) != 96:
            raise ValueError(f"native input must contain 96 rows for {alias}")
        selected = [row for row in rows if row.get("exposure") == "clean"]
        if len(selected) != 48:
            raise ValueError(f"native input must contain 48 clean rows for {alias}")
        for row in selected:
            if row.get("requested_alias") != alias:
                raise ValueError(f"requested alias mismatch in {path}")
            if row.get("api_error"):
                raise ValueError(f"native infrastructure failure retained for {alias}")
            if row.get("status") != "proposal_ready" or not row.get("same_tool_first_proposal"):
                raise ValueError(f"ineligible native proposal: {alias}/{row.get('scenario_id')}")
            if not isinstance(row.get("proposal_effect"), dict):
                raise ValueError(f"missing native proposal effect: {alias}/{row.get('scenario_id')}")
            scenario = scenarios[str(row["scenario_id"])]
            grant = authorized_effect(scenario["workflow"], scenario["authorized_arguments"])
            effect = EffectSpec(**row["proposal_effect"])
            if check_effect(grant, effect).decision != "allow":
                raise ValueError(f"clean proposal is not authorized: {alias}/{row['scenario_id']}")
            if file_sha256(ROOT / scenario["_source_path"]) != row["scenario_sha256"]:
                raise ValueError(f"scenario provenance mismatch: {alias}/{row['scenario_id']}")
            proposals.append(
                {
                    "requested_alias": alias,
                    "scenario_id": row["scenario_id"],
                    "template_id": row["template_id"],
                    "workflow": row["workflow"],
                    "carrier": row["carrier"],
                    "proposal_effect": row["proposal_effect"],
                    "proposal_effect_sha256": value_sha256(row["proposal_effect"]),
                    "scenario_sha256": row["scenario_sha256"],
                    "source_jsonl_sha256": EXPECTED_INPUT_HASHES[alias],
                    "authorized_effect": grant.to_dict(),
                }
            )
    keys = {(item["requested_alias"], item["scenario_id"]) for item in proposals}
    if len(proposals) != 192 or len(keys) != 192:
        raise ValueError("frozen proposal set must contain 192 unique alias/scenario rows")
    return proposals


class AuditedEffectService(ServiceIntegratedEffect):
    """Expose hash-only ledger evidence for the independent artifact audit."""

    def dispatch(
        self, path: str, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        if path == "/health":
            return {"role": "effect", "pid": os.getpid()}
        if path == "/audit-trial":
            return self.audit_trial(str(payload["trial_id"]))
        result = super().dispatch(path, payload, request_received_ns)
        if path in {"/commit-atomic", "/commit-unverified"}:
            result["request_effect_sha256"] = value_sha256(payload["commit_effect"])
        return result

    def audit_trial(self, trial_id: str) -> dict[str, Any]:
        connection = self._connect()
        try:
            state = connection.execute(
                "SELECT effect_json, state_revision FROM authorization_state WHERE trial_id = ?",
                (trial_id,),
            ).fetchone()
            effect = connection.execute(
                "SELECT effect_json FROM effects WHERE trial_id = ?", (trial_id,)
            ).fetchone()
            if state is None:
                raise ValueError(f"unknown trial: {trial_id}")
            counts = self._counts(connection, trial_id)
            authoritative = json.loads(str(state["effect_json"]))
            ledger = json.loads(str(effect["effect_json"])) if effect is not None else None
            return {
                "service_pid": os.getpid(),
                "state_revision": int(state["state_revision"]),
                "authoritative_effect_sha256": value_sha256(authoritative),
                "ledger_effect_sha256": value_sha256(ledger) if ledger is not None else "",
                **counts,
            }
        finally:
            connection.close()


class AuthorizationBridgeService:
    def __init__(self, effect_url: str, authentication_key: bytes):
        self.effect_url = effect_url
        self.authentication_key = authentication_key
        self.lock = threading.Lock()
        self.mutations: dict[str, dict[str, int | None]] = {}

    def dispatch(
        self, path: str, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        if path == "/health":
            return {"role": "authorization", "pid": os.getpid()}
        if path == "/effect-health":
            health = post_json(self.effect_url, "/health", {})
            return {
                "role": "authorization",
                "pid": os.getpid(),
                "effect_role": health["role"],
                "effect_pid": health["pid"],
            }
        if path == "/check":
            return self.check(payload)
        if path == "/revoke":
            return self.revoke(payload, request_received_ns)
        if path == "/mutation-status":
            return self.mutation_status(str(payload["trial_id"]))
        raise ValueError(f"unknown authorization bridge route: {path}")

    def check(self, payload: dict[str, Any]) -> dict[str, Any]:
        trial_id = str(payload["trial_id"])
        authorized = EffectSpec(**payload["authorized_effect"])
        proposed = EffectSpec(**payload["proposal_effect"])
        context = CheckContext(**payload["check_context"])
        receipt = issue_receipt(authorized, proposed, context, self.authentication_key)
        stable = CommitContext(
            context.principal,
            context.authorization_version,
            min(context.expires_at, context.checked_at + 1),
            context.confirmation_nonce,
            False,
        )
        registered = post_json(
            self.effect_url,
            "/register",
            {
                "trial_id": trial_id,
                "effect": proposed.to_dict(),
                "context": {
                    "principal": stable.principal,
                    "authorization_version": stable.authorization_version,
                    "committed_at": stable.committed_at,
                    "confirmation_nonce": stable.confirmation_nonce,
                    "nonce_consumed": stable.nonce_consumed,
                },
            },
        )
        return {
            "authorization_pid": os.getpid(),
            "effect_pid": registered["service_pid"],
            "decision": "allow",
            "receipt": receipt.to_dict(),
            "checked_effect_sha256": value_sha256(receipt.checked_effect.to_dict()),
        }

    def revoke(
        self, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        trial_id = str(payload["trial_id"])
        hold_ms = float(payload["hold_ms"])
        if hold_ms <= 0 or hold_ms > 2000:
            raise ValueError("mutation hold must be in (0, 2000] ms")
        with self.lock:
            if trial_id in self.mutations:
                raise ValueError(f"duplicate mutation: {trial_id}")
            self.mutations[trial_id] = {
                "request_received_ns": request_received_ns,
                "applied_ns": None,
                "completed_ns": None,
                "state_revision": None,
            }
        response = post_json(
            self.effect_url,
            "/mutate",
            {
                "trial_id": trial_id,
                "effect": payload["effect"],
                "context": payload["context"],
            },
        )
        with self.lock:
            state = self.mutations[trial_id]
            state["applied_ns"] = time.perf_counter_ns()
            state["state_revision"] = int(response["state_revision"])
        time.sleep(hold_ms / 1000.0)
        with self.lock:
            state["completed_ns"] = time.perf_counter_ns()
            result = dict(state)
        return {"authorization_pid": os.getpid(), **result}

    def mutation_status(self, trial_id: str) -> dict[str, Any]:
        with self.lock:
            state = self.mutations.get(trial_id)
            if state is None:
                return {
                    "authorization_pid": os.getpid(),
                    "request_received_ns": None,
                    "applied_ns": None,
                    "completed_ns": None,
                    "state_revision": None,
                }
            return {"authorization_pid": os.getpid(), **dict(state)}


class RelayGatewayService:
    def __init__(self, effect_url: str):
        self.effect_url = effect_url

    def dispatch(
        self, path: str, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        if path == "/health":
            return {"role": "gateway", "pid": os.getpid()}
        if path == "/relay-health":
            health = post_json(self.effect_url, "/health", {})
            return {
                "role": "gateway",
                "pid": os.getpid(),
                "effect_role": health["role"],
                "effect_pid": health["pid"],
            }
        if path == "/commit":
            return self.commit(payload, request_received_ns)
        if path == "/audit-trial":
            result = post_json(self.effect_url, "/audit-trial", payload)
            return {"gateway_pid": os.getpid(), **result}
        raise ValueError(f"unknown gateway bridge route: {path}")

    def commit(
        self, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        policy = str(payload["policy"])
        if policy == "cached-pre-action":
            endpoint = "/commit-unverified"
            downstream_policy = "gateway-split"
        elif policy == "receipt-bound":
            endpoint = "/commit-atomic"
            downstream_policy = "service-atomic"
        else:
            raise ValueError(f"unknown bridge policy: {policy}")
        commit_effect = payload["commit_effect"]
        forwarded = {
            "trial_id": str(payload["trial_id"]),
            "policy": downstream_policy,
            "receipt": payload["receipt"],
            "commit_effect": commit_effect,
            "hold_after_verify_ms": 0.0,
        }
        started_ns = time.perf_counter_ns()
        response = post_json(self.effect_url, endpoint, forwarded)
        return {
            "gateway_pid": os.getpid(),
            "effect_pid": response["service_pid"],
            "gateway_request_received_ns": request_received_ns,
            "gateway_total_us": round((time.perf_counter_ns() - started_ns) / 1000.0, 3),
            "gateway_received_effect_sha256": value_sha256(commit_effect),
            "gateway_forwarded_effect_sha256": value_sha256(forwarded["commit_effect"]),
            "effect_request_effect_sha256": response["request_effect_sha256"],
            **{key: value for key, value in response.items() if key != "service_pid"},
        }


def serve_role(
    role: str,
    connection: Any,
    stop_event: Any,
    config: dict[str, Any],
) -> None:
    if role == "effect":
        app: Any = AuditedEffectService(
            pathlib.Path(config["database_path"]), config["authentication_key"]
        )
    elif role == "authorization":
        app = AuthorizationBridgeService(
            config["effect_url"], config["authentication_key"]
        )
    elif role == "gateway":
        app = RelayGatewayService(config["effect_url"])
    else:  # pragma: no cover
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


class NativeServiceCluster:
    def __init__(self, database_path: pathlib.Path, authentication_key: bytes):
        self.database_path = database_path
        self.authentication_key = authentication_key
        self.processes: dict[str, multiprocessing.Process] = {}
        self.events: dict[str, Any] = {}
        self.urls: dict[str, str] = {}
        self.pids: dict[str, int] = {}

    def _start(self, role: str, config: dict[str, Any]) -> str:
        parent, child = multiprocessing.Pipe(duplex=False)
        event = multiprocessing.Event()
        process = multiprocessing.Process(
            target=serve_role,
            args=(role, child, event, config),
            name=f"psebench-native-bridge-{role}",
        )
        process.start()
        child.close()
        if not parent.poll(10):
            process.terminate()
            process.join(timeout=5)
            raise RuntimeError(f"{role} service did not start")
        ready = parent.recv()
        parent.close()
        self.processes[role] = process
        self.events[role] = event
        self.urls[role] = f"http://127.0.0.1:{ready['port']}"
        self.pids[role] = int(ready["pid"])
        health = post_json(self.urls[role], "/health", {})
        if health["role"] != role or int(health["pid"]) != self.pids[role]:
            raise RuntimeError(f"{role} health identity mismatch")
        return self.urls[role]

    def start(self) -> "NativeServiceCluster":
        try:
            effect_url = self._start(
                "effect",
                {
                    "database_path": str(self.database_path),
                    "authentication_key": self.authentication_key,
                },
            )
            authorization_url = self._start(
                "authorization",
                {
                    "effect_url": effect_url,
                    "authentication_key": self.authentication_key,
                },
            )
            gateway_url = self._start("gateway", {"effect_url": effect_url})
            if len(set(self.pids.values())) != 3 or os.getpid() in self.pids.values():
                raise RuntimeError("service roles are not three distinct child processes")
            auth_relay = post_json(authorization_url, "/effect-health", {})
            gateway_relay = post_json(gateway_url, "/relay-health", {})
            if (
                auth_relay["effect_role"] != "effect"
                or int(auth_relay["effect_pid"]) != self.pids["effect"]
                or gateway_relay["effect_role"] != "effect"
                or int(gateway_relay["effect_pid"]) != self.pids["effect"]
            ):
                raise RuntimeError("loopback relay health gate failed")
        except BaseException:
            self.close()
            raise
        return self

    def topology(self, identity_salt: bytes) -> dict[str, Any]:
        commitments = {
            role: hashlib.sha256(
                identity_salt + f":{role}:{self.pids[role]}".encode("ascii")
            ).hexdigest()
            for role in ("authorization", "gateway", "effect")
        }
        return {
            "run_id": RUN_ID,
            "process_count": 3,
            "distinct_processes": 1,
            "loopback_only": 1,
            "health_gate": 1,
            "authorization_effect_relay_gate": 1,
            "gateway_effect_relay_gate": 1,
            "authorization_identity_sha256": commitments["authorization"],
            "gateway_identity_sha256": commitments["gateway"],
            "effect_identity_sha256": commitments["effect"],
            "unique_identity_commitments": int(len(set(commitments.values())) == 3),
        }

    def close(self) -> None:
        for event in self.events.values():
            event.set()
        for url in self.urls.values():
            try:
                post_json(url, "/health", {})
            except Exception:
                pass
        for process in self.processes.values():
            process.join(timeout=5)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        failed = [process.exitcode for process in self.processes.values() if process.exitcode]
        if failed:
            raise RuntimeError(f"service process exited unsuccessfully: {failed}")

    def __enter__(self) -> "NativeServiceCluster":
        return self.start()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def wait_for_active_mutation(
    authorization_url: str, trial_id: str, timeout: float = 10.0
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        status = post_json(
            authorization_url, "/mutation-status", {"trial_id": trial_id}
        )
        if status["applied_ns"] is not None and status["completed_ns"] is None:
            return status
        if time.monotonic() >= deadline:
            raise TimeoutError(f"mutation did not become active: {trial_id}")
        time.sleep(0.0005)


def run_case(
    cluster: NativeServiceCluster,
    proposal: dict[str, Any],
    policy: str,
    state: str,
    *,
    mutation_hold_ms: float = MUTATION_HOLD_MS,
    commit_delay_ms: float = COMMIT_DELAY_MS,
) -> dict[str, Any]:
    if policy not in POLICIES or state not in STATES:
        raise ValueError("invalid policy/state")
    if mutation_hold_ms <= commit_delay_ms:
        raise ValueError("mutation hold must exceed commit delay")
    trial_id = ":".join(
        (RUN_ID, proposal["requested_alias"], proposal["scenario_id"], policy, state)
    )
    base = 2_100_000_000 + int(
        hashlib.sha256(trial_id.encode("utf-8")).hexdigest()[:6], 16
    )
    check_context = {
        "principal": "synthetic-user",
        "authorization_version": 7,
        "checked_at": base,
        "expires_at": base + 60,
        "confirmation_nonce": None,
    }
    checked = post_json(
        cluster.urls["authorization"],
        "/check",
        {
            "trial_id": trial_id,
            "authorized_effect": proposal["authorized_effect"],
            "proposal_effect": proposal["proposal_effect"],
            "check_context": check_context,
        },
    )
    if checked["decision"] != "allow":
        raise RuntimeError(f"authorization unexpectedly blocked: {trial_id}")
    receipt_hash = value_sha256(checked["receipt"]["checked_effect"])
    mutation_response: dict[str, Any] | None = None
    mutation_error: list[BaseException] = []
    mutation_thread: threading.Thread | None = None
    mutation_observed = 0
    mutation_active_precommit = 0
    client_happens_before = 0
    if state == "revoked":
        revoked_context = {
            "principal": "synthetic-user",
            "authorization_version": 8,
            "committed_at": base + 5,
            "confirmation_nonce": None,
            "nonce_consumed": False,
        }
        box: dict[str, Any] = {}

        def mutate_worker() -> None:
            try:
                box["response"] = post_json(
                    cluster.urls["authorization"],
                    "/revoke",
                    {
                        "trial_id": trial_id,
                        "effect": proposal["proposal_effect"],
                        "context": revoked_context,
                        "hold_ms": mutation_hold_ms,
                    },
                )
            except BaseException as exc:  # pragma: no cover - formal failure path
                mutation_error.append(exc)

        mutation_thread = threading.Thread(target=mutate_worker)
        mutation_thread.start()
        observed = wait_for_active_mutation(cluster.urls["authorization"], trial_id)
        mutation_observed = int(
            observed["applied_ns"] is not None
            and observed["completed_ns"] is None
            and int(observed["state_revision"]) == 1
        )
        time.sleep(commit_delay_ms / 1000.0)
        precommit = post_json(
            cluster.urls["authorization"],
            "/mutation-status",
            {"trial_id": trial_id},
        )
        mutation_active_precommit = int(
            precommit["applied_ns"] is not None
            and precommit["completed_ns"] is None
            and int(precommit["state_revision"]) == 1
        )
        if not mutation_observed or not mutation_active_precommit:
            raise RuntimeError(f"mutation-active gate failed: {trial_id}")
        client_happens_before = 1

    started_ns = time.perf_counter_ns()
    committed = post_json(
        cluster.urls["gateway"],
        "/commit",
        {
            "trial_id": trial_id,
            "policy": policy,
            "receipt": checked["receipt"],
            "commit_effect": proposal["proposal_effect"],
        },
    )
    client_commit_us = (time.perf_counter_ns() - started_ns) / 1000.0
    if mutation_thread is not None:
        mutation_thread.join(timeout=mutation_hold_ms / 1000.0 + 5.0)
        if mutation_thread.is_alive():
            raise TimeoutError(f"mutation thread did not finish: {trial_id}")
        if mutation_error:
            raise RuntimeError(f"mutation request failed: {trial_id}: {mutation_error}")
        mutation_response = box["response"]
    audit = post_json(
        cluster.urls["gateway"], "/audit-trial", {"trial_id": trial_id}
    )
    expected_hash = proposal["proposal_effect_sha256"]
    transport_hashes = (
        checked["checked_effect_sha256"],
        receipt_hash,
        committed["gateway_received_effect_sha256"],
        committed["gateway_forwarded_effect_sha256"],
        committed["effect_request_effect_sha256"],
        audit["authoritative_effect_sha256"],
    )
    transport_hash_match = int(all(value == expected_hash for value in transport_hashes))
    effect_rows = int(audit["effect_rows"])
    ledger_hash_match = int(
        (effect_rows == 1 and audit["ledger_effect_sha256"] == expected_hash)
        or (effect_rows == 0 and audit["ledger_effect_sha256"] == "")
    )
    role_chain_verified = int(
        int(checked["authorization_pid"]) == cluster.pids["authorization"]
        and int(checked["effect_pid"]) == cluster.pids["effect"]
        and int(committed["gateway_pid"]) == cluster.pids["gateway"]
        and int(committed["effect_pid"]) == cluster.pids["effect"]
        and int(audit["gateway_pid"]) == cluster.pids["gateway"]
        and int(audit["service_pid"]) == cluster.pids["effect"]
    )
    committed_flag = int(bool(committed["committed"]))
    return {
        "run_id": RUN_ID,
        "requested_alias": proposal["requested_alias"],
        "scenario_id": proposal["scenario_id"],
        "template_id": proposal["template_id"],
        "workflow": proposal["workflow"],
        "carrier": proposal["carrier"],
        "policy": policy,
        "state": state,
        "decision": committed["decision"],
        "reason": committed["reason"],
        "committed": committed_flag,
        "stale_commit": int(state == "revoked" and committed_flag == 1),
        "effect_rows": effect_rows,
        "delivery_attempts": int(audit["delivery_attempts"]),
        "state_revision": int(audit["state_revision"]),
        "mutation_observed_active": mutation_observed,
        "mutation_active_precommit": mutation_active_precommit,
        "commit_after_mutation_observation": client_happens_before,
        "mutation_completed": int(
            state == "revoked"
            and mutation_response is not None
            and mutation_response["completed_ns"] is not None
        ),
        "configured_commit_delay_ms": commit_delay_ms,
        "configured_mutation_hold_ms": mutation_hold_ms,
        "proposal_effect_sha256": expected_hash,
        "authorization_effect_sha256": checked["checked_effect_sha256"],
        "receipt_effect_sha256": receipt_hash,
        "gateway_received_effect_sha256": committed["gateway_received_effect_sha256"],
        "gateway_forwarded_effect_sha256": committed["gateway_forwarded_effect_sha256"],
        "effect_request_effect_sha256": committed["effect_request_effect_sha256"],
        "authoritative_effect_sha256": audit["authoritative_effect_sha256"],
        "ledger_effect_sha256": audit["ledger_effect_sha256"],
        "transport_hash_match": transport_hash_match,
        "ledger_hash_match": ledger_hash_match,
        "role_chain_verified": role_chain_verified,
        "gateway_total_us": float(committed["gateway_total_us"]),
        "client_commit_us": round(client_commit_us, 3),
        "scenario_sha256": proposal["scenario_sha256"],
        "source_jsonl_sha256": proposal["source_jsonl_sha256"],
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["requested_alias"], row["policy"], row["state"])].append(row)
    output: list[dict[str, Any]] = []
    for (alias, policy, state), selected in sorted(groups.items()):
        commits = sum(int(row["committed"]) for row in selected)
        low, high = wilson(commits, len(selected))
        latencies = [float(row["gateway_total_us"]) for row in selected]
        output.append(
            {
                "requested_alias": alias,
                "policy": policy,
                "state": state,
                "n": len(selected),
                "commits": commits,
                "commit_rate": round(commits / len(selected), 6),
                "CI_low": round(low, 6),
                "CI_high": round(high, 6),
                "stale_commits": sum(int(row["stale_commit"]) for row in selected),
                "median_gateway_us": round(statistics.median(latencies), 3),
                "p95_gateway_us": round(percentile(latencies, 0.95), 3),
            }
        )
    return output


def paired(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {
        (row["requested_alias"], row["scenario_id"], row["policy"], row["state"]): row
        for row in rows
    }
    output = []
    for alias in ALIASES:
        ids = sorted(
            {
                row["scenario_id"]
                for row in rows
                if row["requested_alias"] == alias and row["state"] == "revoked"
            }
        )
        b = sum(
            indexed[(alias, scenario_id, "cached-pre-action", "revoked")]["stale_commit"]
            and not indexed[(alias, scenario_id, "receipt-bound", "revoked")]["stale_commit"]
            for scenario_id in ids
        )
        c = sum(
            not indexed[(alias, scenario_id, "cached-pre-action", "revoked")]["stale_commit"]
            and indexed[(alias, scenario_id, "receipt-bound", "revoked")]["stale_commit"]
            for scenario_id in ids
        )
        output.append(
            {
                "requested_alias": alias,
                "n_pairs": len(ids),
                "cached_yes_receipt_no": b,
                "cached_no_receipt_yes": c,
                "exact_mcnemar_p": exact_mcnemar(b, c),
            }
        )
    return output


def integrity(rows: list[dict[str, Any]], cleanup_verified: bool) -> list[dict[str, Any]]:
    revoked = [row for row in rows if row["state"] == "revoked"]
    stable = [row for row in rows if row["state"] == "stable"]
    return [
        {
            "rows": len(rows),
            "unique_keys": len(
                {
                    (
                        row["requested_alias"],
                        row["scenario_id"],
                        row["policy"],
                        row["state"],
                    )
                    for row in rows
                }
            ),
            "aliases": len({row["requested_alias"] for row in rows}),
            "unique_native_proposals": len(
                {(row["requested_alias"], row["scenario_id"]) for row in rows}
            ),
            "stable_rows": len(stable),
            "revoked_rows": len(revoked),
            "revoked_mutation_observed_active": sum(
                int(row["mutation_observed_active"]) for row in revoked
            ),
            "revoked_mutation_active_precommit": sum(
                int(row["mutation_active_precommit"]) for row in revoked
            ),
            "revoked_commit_after_observation": sum(
                int(row["commit_after_mutation_observation"]) for row in revoked
            ),
            "transport_hash_matches": sum(int(row["transport_hash_match"]) for row in rows),
            "ledger_hash_matches": sum(int(row["ledger_hash_match"]) for row in rows),
            "role_chain_verified": sum(int(row["role_chain_verified"]) for row in rows),
            "stable_cached_commits": sum(
                int(row["committed"])
                for row in stable
                if row["policy"] == "cached-pre-action"
            ),
            "stable_receipt_commits": sum(
                int(row["committed"])
                for row in stable
                if row["policy"] == "receipt-bound"
            ),
            "revoked_cached_stale_commits": sum(
                int(row["stale_commit"])
                for row in revoked
                if row["policy"] == "cached-pre-action"
            ),
            "revoked_receipt_stale_commits": sum(
                int(row["stale_commit"])
                for row in revoked
                if row["policy"] == "receipt-bound"
            ),
            "effect_rows": sum(int(row["effect_rows"]) for row in rows),
            "delivery_attempts": sum(int(row["delivery_attempts"]) for row in rows),
            "ephemeral_cleanup_verified": int(cleanup_verified),
        }
    ]


def validate_complete(rows: list[dict[str, Any]]) -> None:
    expected = {
        (alias, scenario_id, policy, state)
        for alias in ALIASES
        for scenario_id in {
            row["scenario_id"] for row in rows if row["requested_alias"] == alias
        }
        for policy in POLICIES
        for state in STATES
    }
    actual = {
        (row["requested_alias"], row["scenario_id"], row["policy"], row["state"])
        for row in rows
    }
    if len(rows) != 768 or len(actual) != 768 or actual != expected:
        raise ValueError(f"incomplete bridge matrix: rows={len(rows)}, keys={len(actual)}")
    for alias in ALIASES:
        alias_rows = [row for row in rows if row["requested_alias"] == alias]
        alias_scenarios = {row["scenario_id"] for row in alias_rows}
        if len(alias_rows) != 192 or len(alias_scenarios) != 48:
            raise ValueError(
                f"alias stratum is incomplete: {alias}, rows={len(alias_rows)}, "
                f"proposals={len(alias_scenarios)}"
            )
    for row in rows:
        expected_commit = int(
            row["state"] == "stable" or row["policy"] == "cached-pre-action"
        )
        if row["committed"] != expected_commit or row["effect_rows"] != expected_commit:
            raise ValueError(f"unexpected commit outcome: {row['requested_alias']}/{row['scenario_id']}")
        if row["delivery_attempts"] != 1:
            raise ValueError(f"unexpected delivery count: {row['requested_alias']}/{row['scenario_id']}")
        if (
            row["configured_commit_delay_ms"] != COMMIT_DELAY_MS
            or row["configured_mutation_hold_ms"] != MUTATION_HOLD_MS
        ):
            raise ValueError(f"formal timing configuration changed: {row['scenario_id']}")
        if not row["transport_hash_match"] or not row["ledger_hash_match"]:
            raise ValueError(f"effect hash chain mismatch: {row['requested_alias']}/{row['scenario_id']}")
        if not row["role_chain_verified"]:
            raise ValueError(f"service identity chain mismatch: {row['requested_alias']}/{row['scenario_id']}")
        if row["state"] == "revoked" and not (
            row["mutation_observed_active"]
            and row["mutation_active_precommit"]
            and row["commit_after_mutation_observation"]
            and row["mutation_completed"]
            and row["state_revision"] == 1
        ):
            raise ValueError(f"revocation happens-before gate failed: {row['scenario_id']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=pathlib.Path, default=ROOT / "analysis")
    parser.add_argument(
        "--manifest",
        type=pathlib.Path,
        default=ROOT / "scenarios" / "same-tool-native-holdout" / "MANIFEST.csv",
    )
    parser.add_argument(
        "--output-root",
        type=pathlib.Path,
        default=ROOT / "results" / "native_service_commit_bridge",
    )
    parser.add_argument(
        "--analysis-prefix",
        type=pathlib.Path,
        default=ROOT / "analysis" / "native_service_commit_bridge",
    )
    args = parser.parse_args()
    final_jsonl = args.output_root / "native_service_commit_bridge.jsonl"
    attempts_jsonl = args.output_root / "native_service_commit_bridge_attempts.jsonl"
    output_paths = [
        final_jsonl,
        attempts_jsonl,
        pathlib.Path(f"{args.analysis_prefix}_detail.csv"),
        pathlib.Path(f"{args.analysis_prefix}_summary.csv"),
        pathlib.Path(f"{args.analysis_prefix}_paired.csv"),
        pathlib.Path(f"{args.analysis_prefix}_integrity.csv"),
        pathlib.Path(f"{args.analysis_prefix}_topology.csv"),
    ]
    if any(path.exists() for path in output_paths):
        raise SystemExit("formal output exists; a dated amendment and fresh prefix are required")

    proposals = load_frozen_proposals(args.input_root, args.manifest)
    rows: list[dict[str, Any]] = []
    key = secrets.token_bytes(32)
    identity_salt = secrets.token_bytes(32)
    temporary_path: pathlib.Path | None = None
    topology: dict[str, Any] | None = None
    with tempfile.TemporaryDirectory(prefix="psebench-native-service-bridge-") as directory:
        temporary_path = pathlib.Path(directory)
        database_path = temporary_path / "effect.sqlite"
        with NativeServiceCluster(database_path, key) as cluster:
            topology = cluster.topology(identity_salt)
            for proposal in proposals:
                for policy in POLICIES:
                    for state in STATES:
                        try:
                            row = run_case(cluster, proposal, policy, state)
                        except BaseException as exc:
                            append_jsonl(
                                attempts_jsonl,
                                {
                                    "run_id": RUN_ID,
                                    "requested_alias": proposal["requested_alias"],
                                    "scenario_id": proposal["scenario_id"],
                                    "policy": policy,
                                    "state": state,
                                    "status": "infrastructure_or_gate_failure",
                                    "error_type": type(exc).__name__,
                                    "error": str(exc),
                                },
                            )
                            raise
                        append_jsonl(attempts_jsonl, {"status": "complete", **row})
                        rows.append(row)
            validate_complete(rows)
    cleanup_verified = bool(temporary_path is not None and not temporary_path.exists())
    if not cleanup_verified:
        raise RuntimeError("temporary database/key directory cleanup was not verified")
    assert topology is not None
    write_jsonl(final_jsonl, rows)
    write_csv(pathlib.Path(f"{args.analysis_prefix}_detail.csv"), rows)
    write_csv(pathlib.Path(f"{args.analysis_prefix}_summary.csv"), summarize(rows))
    write_csv(pathlib.Path(f"{args.analysis_prefix}_paired.csv"), paired(rows))
    write_csv(
        pathlib.Path(f"{args.analysis_prefix}_integrity.csv"),
        integrity(rows, cleanup_verified),
    )
    write_csv(pathlib.Path(f"{args.analysis_prefix}_topology.csv"), [topology])
    print(
        "completed 768 native-proposal three-process commit observations; "
        f"detail={args.analysis_prefix}_detail.csv"
    )


if __name__ == "__main__":
    main()
