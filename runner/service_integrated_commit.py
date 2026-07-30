"""Service-integrated receipt verification and atomic effect commit.

This module keeps the authoritative commit state and effect ledger in one
SQLite database. Each request uses its own connection so mutation and commit
requests contend on the database write lock rather than a Python-only mutex.
"""

from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import threading
import time
from typing import Any

from commit_binding import CommitContext, CommitReceipt, verify_commit
from effect_boundary import EffectSpec


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


class ServiceIntegratedEffect:
    """HTTP-app-compatible effect service with transaction-bound verification."""

    def __init__(
        self,
        database_path: pathlib.Path,
        authentication_key: bytes,
        *,
        busy_timeout_ms: int = 20_000,
    ):
        if len(authentication_key) < 16:
            raise ValueError("authentication key must contain at least 16 bytes")
        if busy_timeout_ms < 1:
            raise ValueError("busy timeout must be positive")
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path
        self.authentication_key = authentication_key
        self.busy_timeout_ms = busy_timeout_ms
        self.telemetry_lock = threading.Lock()
        self.telemetry: dict[str, dict[str, int | None]] = {}
        connection = self._connect()
        try:
            connection.executescript(
                """
                CREATE TABLE authorization_state (
                    trial_id TEXT PRIMARY KEY,
                    effect_json TEXT NOT NULL,
                    principal TEXT NOT NULL,
                    authorization_version INTEGER NOT NULL,
                    committed_at INTEGER NOT NULL,
                    confirmation_nonce TEXT,
                    nonce_consumed INTEGER NOT NULL CHECK (nonce_consumed IN (0, 1)),
                    state_revision INTEGER NOT NULL
                );
                CREATE TABLE linearization_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    trial_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    state_revision INTEGER NOT NULL
                );
                CREATE TABLE effects (
                    trial_id TEXT PRIMARY KEY,
                    policy TEXT NOT NULL,
                    effect_json TEXT NOT NULL,
                    state_revision INTEGER NOT NULL,
                    linearization_sequence INTEGER NOT NULL,
                    FOREIGN KEY(linearization_sequence)
                        REFERENCES linearization_events(sequence)
                );
                CREATE TABLE commit_attempts (
                    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trial_id TEXT NOT NULL,
                    policy TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    state_revision INTEGER NOT NULL,
                    idempotent_replay INTEGER NOT NULL
                        CHECK (idempotent_replay IN (0, 1))
                );
                CREATE TABLE nonce_consumptions (
                    nonce TEXT PRIMARY KEY,
                    trial_id TEXT NOT NULL UNIQUE
                );
                """
            )
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=self.busy_timeout_ms / 1000.0,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def _set_telemetry(self, trial_id: str, **values: int | None) -> None:
        with self.telemetry_lock:
            state = self.telemetry.setdefault(trial_id, {})
            state.update(values)

    def _telemetry(self, trial_id: str) -> dict[str, int | None]:
        with self.telemetry_lock:
            return dict(self.telemetry.get(trial_id, {}))

    @staticmethod
    def _context_from_row(row: sqlite3.Row) -> CommitContext:
        return CommitContext(
            principal=str(row["principal"]),
            authorization_version=int(row["authorization_version"]),
            committed_at=int(row["committed_at"]),
            confirmation_nonce=row["confirmation_nonce"],
            nonce_consumed=bool(row["nonce_consumed"]),
        )

    @staticmethod
    def _effect_from_row(row: sqlite3.Row) -> EffectSpec:
        return EffectSpec(**json.loads(str(row["effect_json"])))

    @staticmethod
    def _begin(connection: sqlite3.Connection) -> None:
        connection.execute("BEGIN IMMEDIATE")

    def dispatch(
        self, path: str, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        if path == "/health":
            return {"role": "service-integrated-effect", "pid": os.getpid()}
        if path == "/register":
            return self.register(payload)
        if path == "/state":
            return self.state(str(payload["trial_id"]))
        if path == "/status":
            return {"service_pid": os.getpid(), **self._telemetry(str(payload["trial_id"]))}
        if path == "/mutate":
            return self.mutate(payload, request_received_ns)
        if path == "/commit-atomic":
            return self.commit_atomic(payload, request_received_ns)
        if path == "/commit-unverified":
            return self.commit_unverified(payload, request_received_ns)
        if path == "/count":
            return self.count(str(payload["trial_id"]))
        raise ValueError(f"unknown integrated effect route: {path}")

    def register(self, payload: dict[str, Any]) -> dict[str, Any]:
        trial_id = str(payload["trial_id"])
        effect = EffectSpec(**payload["effect"])
        context = CommitContext(**payload["context"])
        connection = self._connect()
        try:
            self._begin(connection)
            connection.execute(
                """
                INSERT INTO authorization_state VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    trial_id,
                    json.dumps(effect.to_dict(), sort_keys=True),
                    context.principal,
                    context.authorization_version,
                    context.committed_at,
                    context.confirmation_nonce,
                    int(context.nonce_consumed),
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        self._set_telemetry(
            trial_id,
            verification_completed_ns=None,
            effect_transaction_started_ns=None,
            effect_transaction_committed_ns=None,
            mutation_requested_ns=None,
            mutation_lock_acquired_ns=None,
            mutation_applied_ns=None,
        )
        return {"trial_id": trial_id, "service_pid": os.getpid(), "state_revision": 0}

    def state(self, trial_id: str) -> dict[str, Any]:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM authorization_state WHERE trial_id = ?", (trial_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown trial: {trial_id}")
            return {
                "service_pid": os.getpid(),
                "effect": self._effect_from_row(row).to_dict(),
                "context": {
                    "principal": row["principal"],
                    "authorization_version": int(row["authorization_version"]),
                    "committed_at": int(row["committed_at"]),
                    "confirmation_nonce": row["confirmation_nonce"],
                    "nonce_consumed": bool(row["nonce_consumed"]),
                },
                "state_revision": int(row["state_revision"]),
            }
        finally:
            connection.close()

    def mutate(
        self, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        trial_id = str(payload["trial_id"])
        effect = EffectSpec(**payload["effect"])
        context = CommitContext(**payload["context"])
        self._set_telemetry(trial_id, mutation_requested_ns=request_received_ns)
        connection = self._connect()
        try:
            self._begin(connection)
            acquired_ns = time.perf_counter_ns()
            self._set_telemetry(trial_id, mutation_lock_acquired_ns=acquired_ns)
            current = connection.execute(
                "SELECT state_revision FROM authorization_state WHERE trial_id = ?",
                (trial_id,),
            ).fetchone()
            if current is None:
                raise ValueError(f"unknown trial: {trial_id}")
            revision = int(current["state_revision"]) + 1
            connection.execute(
                """
                UPDATE authorization_state
                SET effect_json = ?, principal = ?, authorization_version = ?,
                    committed_at = ?, confirmation_nonce = ?, nonce_consumed = ?,
                    state_revision = ?
                WHERE trial_id = ?
                """,
                (
                    json.dumps(effect.to_dict(), sort_keys=True),
                    context.principal,
                    context.authorization_version,
                    context.committed_at,
                    context.confirmation_nonce,
                    int(context.nonce_consumed),
                    revision,
                    trial_id,
                ),
            )
            cursor = connection.execute(
                "INSERT INTO linearization_events (trial_id, event_type, state_revision) VALUES (?, ?, ?)",
                (trial_id, "mutation", revision),
            )
            sequence = int(cursor.lastrowid)
            connection.commit()
            applied_ns = time.perf_counter_ns()
            self._set_telemetry(trial_id, mutation_applied_ns=applied_ns)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {
            "service_pid": os.getpid(),
            "state_revision": revision,
            "mutation_sequence": sequence,
            "lock_wait_us": round((acquired_ns - request_received_ns) / 1000.0, 3),
        }

    def _counts(self, connection: sqlite3.Connection, trial_id: str) -> dict[str, Any]:
        attempts = int(
            connection.execute(
                "SELECT COUNT(*) FROM commit_attempts WHERE trial_id = ?", (trial_id,)
            ).fetchone()[0]
        )
        effect = connection.execute(
            "SELECT linearization_sequence FROM effects WHERE trial_id = ?", (trial_id,)
        ).fetchone()
        mutation = connection.execute(
            """
            SELECT MAX(sequence) FROM linearization_events
            WHERE trial_id = ? AND event_type = 'mutation'
            """,
            (trial_id,),
        ).fetchone()[0]
        nonces = int(
            connection.execute(
                "SELECT COUNT(*) FROM nonce_consumptions WHERE trial_id = ?", (trial_id,)
            ).fetchone()[0]
        )
        return {
            "delivery_attempts": attempts,
            "effect_rows": int(effect is not None),
            "effect_sequence": int(effect[0]) if effect is not None else None,
            "mutation_sequence": int(mutation) if mutation is not None else None,
            "nonce_rows": nonces,
        }

    def count(self, trial_id: str) -> dict[str, Any]:
        connection = self._connect()
        try:
            return {"service_pid": os.getpid(), **self._counts(connection, trial_id)}
        finally:
            connection.close()

    def _record_attempt(
        self,
        connection: sqlite3.Connection,
        *,
        trial_id: str,
        policy: str,
        decision: str,
        reason: str,
        state_revision: int,
        idempotent_replay: bool,
    ) -> None:
        connection.execute(
            """
            INSERT INTO commit_attempts
                (trial_id, policy, decision, reason, state_revision, idempotent_replay)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                trial_id,
                policy,
                decision,
                reason,
                state_revision,
                int(idempotent_replay),
            ),
        )

    def commit_atomic(
        self, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        trial_id = str(payload["trial_id"])
        policy = str(payload["policy"])
        if policy != "service-atomic":
            raise ValueError("atomic endpoint requires service-atomic policy")
        hold_ms = float(payload.get("hold_after_verify_ms", 0.0))
        if hold_ms < 0 or hold_ms > 50:
            raise ValueError("post-verification hold must be between 0 and 50 ms")
        receipt = receipt_from_dict(payload["receipt"])
        commit_effect = EffectSpec(**payload["commit_effect"])
        connection = self._connect()
        try:
            self._begin(connection)
            transaction_started_ns = time.perf_counter_ns()
            self._set_telemetry(
                trial_id, effect_transaction_started_ns=transaction_started_ns
            )
            state = connection.execute(
                "SELECT * FROM authorization_state WHERE trial_id = ?", (trial_id,)
            ).fetchone()
            if state is None:
                raise ValueError(f"unknown trial: {trial_id}")
            revision = int(state["state_revision"])
            existing = connection.execute(
                "SELECT linearization_sequence FROM effects WHERE trial_id = ?",
                (trial_id,),
            ).fetchone()
            if existing is not None:
                decision = "allow"
                reason = "same trial already committed"
                idempotent = True
                self._record_attempt(
                    connection,
                    trial_id=trial_id,
                    policy=policy,
                    decision=decision,
                    reason=reason,
                    state_revision=revision,
                    idempotent_replay=True,
                )
            else:
                idempotent = False
                current_effect = self._effect_from_row(state)
                context = self._context_from_row(state)
                bound = verify_commit(
                    receipt, commit_effect, context, self.authentication_key
                )
                decision = bound.decision
                reason = bound.reason
                verified_ns = time.perf_counter_ns()
                self._set_telemetry(
                    trial_id, verification_completed_ns=verified_ns
                )
                if decision == "allow" and current_effect != commit_effect:
                    decision = "block"
                    reason = "authoritative effect differs from commit effect"
                if decision == "allow" and hold_ms:
                    time.sleep(hold_ms / 1000.0)
                if decision == "allow" and receipt.confirmation_nonce is not None:
                    try:
                        connection.execute(
                            "INSERT INTO nonce_consumptions (nonce, trial_id) VALUES (?, ?)",
                            (receipt.confirmation_nonce, trial_id),
                        )
                    except sqlite3.IntegrityError:
                        decision = "block"
                        reason = "confirmation nonce was already consumed"
                if decision == "allow":
                    cursor = connection.execute(
                        """
                        INSERT INTO linearization_events
                            (trial_id, event_type, state_revision)
                        VALUES (?, ?, ?)
                        """,
                        (trial_id, "effect_commit", revision),
                    )
                    sequence = int(cursor.lastrowid)
                    connection.execute(
                        "INSERT INTO effects VALUES (?, ?, ?, ?, ?)",
                        (
                            trial_id,
                            policy,
                            json.dumps(commit_effect.to_dict(), sort_keys=True),
                            revision,
                            sequence,
                        ),
                    )
                    if receipt.confirmation_nonce is not None:
                        connection.execute(
                            "UPDATE authorization_state SET nonce_consumed = 1 WHERE trial_id = ?",
                            (trial_id,),
                        )
                self._record_attempt(
                    connection,
                    trial_id=trial_id,
                    policy=policy,
                    decision=decision,
                    reason=reason,
                    state_revision=revision,
                    idempotent_replay=False,
                )
            connection.commit()
            committed_ns = time.perf_counter_ns()
            self._set_telemetry(
                trial_id, effect_transaction_committed_ns=committed_ns
            )
            counts = self._counts(connection, trial_id)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {
            "service_pid": os.getpid(),
            "decision": decision,
            "reason": reason,
            "committed": counts["effect_rows"] == 1,
            "idempotent_replay": int(idempotent),
            "request_received_ns": request_received_ns,
            **counts,
        }

    def commit_unverified(
        self, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        trial_id = str(payload["trial_id"])
        policy = str(payload["policy"])
        if policy != "gateway-split":
            raise ValueError("unverified endpoint requires gateway-split policy")
        commit_effect = EffectSpec(**payload["commit_effect"])
        connection = self._connect()
        try:
            self._begin(connection)
            state = connection.execute(
                "SELECT state_revision FROM authorization_state WHERE trial_id = ?",
                (trial_id,),
            ).fetchone()
            if state is None:
                raise ValueError(f"unknown trial: {trial_id}")
            revision = int(state["state_revision"])
            existing = connection.execute(
                "SELECT linearization_sequence FROM effects WHERE trial_id = ?",
                (trial_id,),
            ).fetchone()
            if existing is None:
                cursor = connection.execute(
                    """
                    INSERT INTO linearization_events
                        (trial_id, event_type, state_revision)
                    VALUES (?, ?, ?)
                    """,
                    (trial_id, "effect_commit", revision),
                )
                sequence = int(cursor.lastrowid)
                connection.execute(
                    "INSERT INTO effects VALUES (?, ?, ?, ?, ?)",
                    (
                        trial_id,
                        policy,
                        json.dumps(commit_effect.to_dict(), sort_keys=True),
                        revision,
                        sequence,
                    ),
                )
                idempotent = False
                reason = "gateway allow accepted without service-side revalidation"
            else:
                idempotent = True
                reason = "same trial already committed"
            self._record_attempt(
                connection,
                trial_id=trial_id,
                policy=policy,
                decision="allow",
                reason=reason,
                state_revision=revision,
                idempotent_replay=idempotent,
            )
            connection.commit()
            counts = self._counts(connection, trial_id)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {
            "service_pid": os.getpid(),
            "decision": "allow",
            "reason": reason,
            "committed": True,
            "idempotent_replay": int(idempotent),
            "request_received_ns": request_received_ns,
            **counts,
        }
