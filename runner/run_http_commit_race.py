#!/usr/bin/env python3
"""Execute frozen check-to-commit transitions across local HTTP boundaries."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import pathlib
import secrets
import sqlite3
import sys
import threading
import time
from typing import Any
from urllib.request import Request, urlopen

import yaml


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
from replay_commit_race import POLICIES  # noqa: E402


EXPECTED_FAMILIES = {
    "authorization-revocation",
    "confirmation-replay",
    "effect-substitution",
    "lease-expiry",
    "principal-switch",
}


@dataclass
class Trial:
    policy: str
    receipt: CommitReceipt
    current_effect: EffectSpec
    current_context: CommitContext
    lock: threading.Lock = field(default_factory=threading.Lock)
    mutation_request_received_ns: int | None = None
    mutation_applied_ns: int | None = None
    mutation_completed_ns: int | None = None


class CommitRaceStore:
    """Thread-safe mutable authorization state plus an observable SQLite ledger."""

    def __init__(self, database: pathlib.Path, authentication_key: bytes):
        database.parent.mkdir(parents=True, exist_ok=True)
        self.authentication_key = authentication_key
        self.trials: dict[str, Trial] = {}
        self.trials_lock = threading.Lock()
        self.database_lock = threading.Lock()
        self.database = sqlite3.connect(database, check_same_thread=False)
        self.database.execute(
            """
            CREATE TABLE commits (
                trial_id TEXT PRIMARY KEY,
                policy TEXT NOT NULL,
                effect_json TEXT NOT NULL,
                valid_at_commit INTEGER NOT NULL,
                committed_ns INTEGER NOT NULL
            )
            """
        )
        self.database.commit()

    def close(self) -> None:
        self.database.close()

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
        initial_context = CommitContext(
            principal=context.principal,
            authorization_version=context.authorization_version,
            committed_at=committed_at,
            confirmation_nonce=context.confirmation_nonce,
            nonce_consumed=False,
        )
        trial = Trial(policy, receipt, checked, initial_context)
        with self.trials_lock:
            if trial_id in self.trials:
                raise ValueError(f"duplicate trial: {trial_id}")
            self.trials[trial_id] = trial
        return {
            "trial_id": trial_id,
            "decision": "allow",
            "receipt_tag": receipt.authentication_tag,
            "checked_ns": time.perf_counter_ns(),
        }

    def _trial(self, trial_id: str) -> Trial:
        with self.trials_lock:
            try:
                return self.trials[trial_id]
            except KeyError as exc:
                raise ValueError(f"unknown trial: {trial_id}") from exc

    def mutate(
        self, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        trial_id = str(payload["trial_id"])
        hold_ms = float(payload.get("hold_ms", 0.0))
        if hold_ms < 0 or hold_ms > 1000:
            raise ValueError("hold_ms must be between 0 and 1000")
        trial = self._trial(trial_id)
        with trial.lock:
            trial.mutation_request_received_ns = request_received_ns
            trial.current_effect = EffectSpec(**payload["commit_effect"])
            trial.current_context = CommitContext(**payload["commit_context"])
            trial.mutation_applied_ns = time.perf_counter_ns()
            time.sleep(hold_ms / 1000.0)
            trial.mutation_completed_ns = time.perf_counter_ns()
            return {
                "trial_id": trial_id,
                "mutation_request_received_ns": trial.mutation_request_received_ns,
                "mutation_applied_ns": trial.mutation_applied_ns,
                "mutation_completed_ns": trial.mutation_completed_ns,
            }

    def commit(
        self, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        trial_id = str(payload["trial_id"])
        trial = self._trial(trial_id)
        with trial.lock:
            serialized_ns = time.perf_counter_ns()
            bound = verify_commit(
                trial.receipt,
                trial.current_effect,
                trial.current_context,
                self.authentication_key,
            )
            valid_at_commit = bound.decision == "allow"
            decision = "allow" if trial.policy == "check-once" else bound.decision
            committed = decision == "allow"
            if committed:
                with self.database_lock:
                    self.database.execute(
                        "INSERT INTO commits VALUES (?, ?, ?, ?, ?)",
                        (
                            trial_id,
                            trial.policy,
                            json.dumps(
                                trial.current_effect.to_dict(), sort_keys=True
                            ),
                            int(valid_at_commit),
                            serialized_ns,
                        ),
                    )
                    self.database.commit()
            ledger_rows = self.ledger_count(trial_id)
            mutation_before_commit = (
                trial.mutation_applied_ns is not None
                and trial.mutation_applied_ns <= serialized_ns
            )
            request_overlap = (
                trial.mutation_request_received_ns is not None
                and trial.mutation_completed_ns is not None
                and trial.mutation_request_received_ns
                <= request_received_ns
                <= trial.mutation_completed_ns
            )
            return {
                "trial_id": trial_id,
                "policy": trial.policy,
                "decision": decision,
                "reason": (
                    "cached check-time allow"
                    if trial.policy == "check-once"
                    else bound.reason
                ),
                "binding_decision": bound.decision,
                "binding_reason": bound.reason,
                "valid_at_commit": valid_at_commit,
                "committed": committed,
                "ledger_rows": ledger_rows,
                "commit_request_received_ns": request_received_ns,
                "commit_serialized_ns": serialized_ns,
                "mutation_before_commit": mutation_before_commit,
                "request_overlap": request_overlap,
            }

    def ledger_count(self, trial_id: str) -> int:
        with self.database_lock:
            row = self.database.execute(
                "SELECT COUNT(*) FROM commits WHERE trial_id = ?", (trial_id,)
            ).fetchone()
        return int(row[0])


class CommitRaceHandler(BaseHTTPRequestHandler):
    server: "CommitRaceHTTPServer"

    def do_POST(self) -> None:  # noqa: N802
        received_ns = time.perf_counter_ns()
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 1024 * 1024:
                raise ValueError("invalid JSON body length")
            payload = json.loads(self.rfile.read(length))
            if self.path == "/check":
                result = self.server.store.check(payload)
            elif self.path == "/mutate":
                result = self.server.store.mutate(payload, received_ns)
            elif self.path == "/commit":
                result = self.server.store.commit(payload, received_ns)
            else:
                self.send_error(404)
                return
            body = json.dumps(result, sort_keys=True).encode("utf-8")
            self.send_response(200)
        except Exception as exc:  # pragma: no cover - exercised by CLI failures
            body = json.dumps({"error": str(exc)}, sort_keys=True).encode("utf-8")
            self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class CommitRaceHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], store: CommitRaceStore):
        super().__init__(address, CommitRaceHandler)
        self.store = store


def post_json(base_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    request = Request(
        base_url + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        result = json.loads(response.read())
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def start_server(store: CommitRaceStore) -> tuple[CommitRaceHTTPServer, threading.Thread, str]:
    server = CommitRaceHTTPServer(("127.0.0.1", 0), store)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def load_scenarios(directory: pathlib.Path) -> list[dict[str, Any]]:
    scenarios = [
        yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.yaml"))
    ]
    if len(scenarios) != 150:
        raise ValueError(f"expected 150 frozen scenarios, found {len(scenarios)}")
    if len({scenario["id"] for scenario in scenarios}) != len(scenarios):
        raise ValueError("duplicate scenario IDs in frozen commit-race corpus")
    families = {scenario["family"] for scenario in scenarios}
    if families != EXPECTED_FAMILIES:
        raise ValueError(f"unexpected transition families: {sorted(families)}")
    for family in EXPECTED_FAMILIES:
        selected = [item for item in scenarios if item["family"] == family]
        attacks = sum(item["type"] == "attack" for item in selected)
        controls = sum(item["type"] == "benign" for item in selected)
        if (attacks, controls) != (20, 10):
            raise ValueError(
                f"unexpected {family} composition: attacks={attacks}, controls={controls}"
            )
    return scenarios


def run_one(
    base_url: str,
    policy: str,
    scenario: dict[str, Any],
    *,
    commit_delay_ms: float,
    mutation_hold_ms: float,
) -> dict[str, Any]:
    scenario_id = str(scenario["id"])
    trial_id = f"{policy}:{scenario_id}"
    race = scenario["commit_race"]
    check_response = post_json(
        base_url,
        "/check",
        {
            "trial_id": trial_id,
            "policy": policy,
            "authorized_effect": race["authorized_effect"],
            "checked_effect": race["checked_effect"],
            "check_context": race["check_context"],
        },
    )
    mutation_response: dict[str, Any] | None = None
    if scenario["type"] == "attack":
        barrier = threading.Barrier(3)
        responses: dict[str, dict[str, Any]] = {}
        errors: list[BaseException] = []

        def mutate_worker() -> None:
            try:
                barrier.wait()
                responses["mutation"] = post_json(
                    base_url,
                    "/mutate",
                    {
                        "trial_id": trial_id,
                        "commit_effect": race["commit_effect"],
                        "commit_context": race["commit_context"],
                        "hold_ms": mutation_hold_ms,
                    },
                )
            except BaseException as exc:
                errors.append(exc)

        def commit_worker() -> None:
            try:
                barrier.wait()
                time.sleep(commit_delay_ms / 1000.0)
                responses["commit"] = post_json(
                    base_url, "/commit", {"trial_id": trial_id}
                )
            except BaseException as exc:
                errors.append(exc)

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
        commit_response = responses["commit"]
    else:
        commit_response = post_json(base_url, "/commit", {"trial_id": trial_id})

    committed = bool(commit_response["committed"])
    valid_at_commit = bool(commit_response["valid_at_commit"])
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
        "ledger_rows": int(commit_response["ledger_rows"]),
        "mutation_before_commit": int(commit_response["mutation_before_commit"]),
        "request_overlap": int(commit_response["request_overlap"]),
        "binding_decision": commit_response["binding_decision"],
        "policy_decision": commit_response["decision"],
        "check_response": check_response,
        "mutation_response": mutation_response,
        "commit_response": commit_response,
    }


def wilson(k: int, n: int) -> tuple[float, float]:
    if not n:
        return 0.0, 0.0
    z = 1.96
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def exact_mcnemar(b: int, c: int) -> float:
    discordant = b + c
    if not discordant:
        return 1.0
    tail = sum(math.comb(discordant, index) for index in range(min(b, c) + 1))
    return min(1.0, 2 * tail / (2**discordant))


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
                "attack_request_overlap": sum(item["request_overlap"] for item in attacks),
            }
        )
    return output


def paired(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {(row["policy"], row["scenario_id"]): row for row in rows}
    attack_rows = [row for row in rows if row["scenario_type"] == "attack"]
    output = []
    for family in ["all", *sorted(EXPECTED_FAMILIES)]:
        ids = sorted(
            {
                row["scenario_id"]
                for row in attack_rows
                if family == "all" or row["family"] == family
            }
        )
        for scenario_id in ids:
            for policy in POLICIES:
                if (policy, scenario_id) not in indexed:
                    raise ValueError(f"missing pair: {policy}/{scenario_id}")
        b = sum(
            indexed[("check-once", item)]["attack"]
            and not indexed[("commit-bound", item)]["attack"]
            for item in ids
        )
        c = sum(
            not indexed[("check-once", item)]["attack"]
            and indexed[("commit-bound", item)]["attack"]
            for item in ids
        )
        output.append(
            {
                "family": family,
                "n_pairs": len(ids),
                "check_once_yes_commit_bound_no": b,
                "check_once_no_commit_bound_yes": c,
                "exact_mcnemar_p": exact_mcnemar(b, c),
            }
        )
    return output


def validate_complete(rows: list[dict[str, Any]], scenarios: list[dict[str, Any]]) -> None:
    expected_ids = {str(item["id"]) for item in scenarios}
    expected_keys = {(policy, item) for policy in POLICIES for item in expected_ids}
    actual_keys = {(row["policy"], row["scenario_id"]) for row in rows}
    if len(rows) != 300 or actual_keys != expected_keys:
        raise ValueError(
            f"incomplete matrix: rows={len(rows)}, missing={sorted(expected_keys - actual_keys)[:5]}"
        )
    for row in rows:
        expected_ledger = 1 if row["committed"] else 0
        if row["ledger_rows"] != expected_ledger:
            raise ValueError(f"ledger mismatch for {row['policy']}/{row['scenario_id']}")
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
        default=ROOT / "results" / "http_commit_race",
    )
    parser.add_argument(
        "--analysis-prefix",
        type=pathlib.Path,
        default=ROOT / "analysis" / "http_commit_race",
    )
    parser.add_argument("--commit-delay-ms", type=float, default=1.0)
    parser.add_argument("--mutation-hold-ms", type=float, default=3.0)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.commit_delay_ms < 0 or args.mutation_hold_ms <= args.commit_delay_ms:
        raise SystemExit("mutation hold must be positive and exceed commit delay")

    scenarios = load_scenarios(args.scenario_dir)
    raw_path = args.output_root / "http_commit_race.jsonl"
    database_path = args.output_root / "sandbox.sqlite"
    if (raw_path.exists() or database_path.exists()) and not args.overwrite:
        raise SystemExit("output exists; pass --overwrite for a fresh complete matrix")
    args.output_root.mkdir(parents=True, exist_ok=True)
    if raw_path.exists():
        raw_path.unlink()
    if database_path.exists():
        database_path.unlink()

    store = CommitRaceStore(database_path, secrets.token_bytes(32))
    server, server_thread, base_url = start_server(store)
    rows: list[dict[str, Any]] = []
    try:
        for policy in POLICIES:
            for scenario in scenarios:
                rows.append(
                    run_one(
                        base_url,
                        policy,
                        scenario,
                        commit_delay_ms=args.commit_delay_ms,
                        mutation_hold_ms=args.mutation_hold_ms,
                    )
                )
        validate_complete(rows, scenarios)
        raw_path.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
        details = [
            {key: value for key, value in row.items() if not key.endswith("_response")}
            for row in rows
        ]
        write_csv(pathlib.Path(f"{args.analysis_prefix}_detail.csv"), details)
        write_csv(pathlib.Path(f"{args.analysis_prefix}_summary.csv"), summarize(rows))
        write_csv(pathlib.Path(f"{args.analysis_prefix}_paired.csv"), paired(rows))
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
        store.close()
    print(
        "completed 300 local HTTP policy/scenario observations; "
        "timing and SQLite ledger checks passed"
    )


if __name__ == "__main__":
    main()
