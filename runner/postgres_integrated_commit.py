"""PostgreSQL realization of service-integrated receipt verification."""

from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Any
from urllib.parse import urlparse

try:
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except ImportError:  # pragma: no cover - exercised by dependency readiness checks
    psycopg = None
    sql = None
    dict_row = None
    Jsonb = None

from commit_binding import CommitContext, verify_commit
from effect_boundary import EffectSpec
from service_integrated_commit import receipt_from_dict


SCHEMA_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def require_psycopg() -> None:
    if psycopg is None:
        raise RuntimeError("psycopg is required for the PostgreSQL portability path")


def validate_schema_name(value: str) -> str:
    if not SCHEMA_PATTERN.fullmatch(value):
        raise ValueError("schema must be a lowercase PostgreSQL identifier")
    return value


def validate_loopback_dsn(dsn: str) -> str:
    parsed = urlparse(dsn)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("PostgreSQL DSN must use postgres or postgresql")
    if parsed.hostname not in LOOPBACK_HOSTS:
        raise ValueError("PostgreSQL portability service must be loopback-only")
    if not parsed.path or parsed.path == "/":
        raise ValueError("PostgreSQL DSN must name a database")
    return dsn


def _admin_connection(dsn: str) -> Any:
    require_psycopg()
    return psycopg.connect(dsn, autocommit=True, row_factory=dict_row)


def drop_postgres_schema(dsn: str, schema: str) -> None:
    validate_loopback_dsn(dsn)
    validate_schema_name(schema)
    connection = _admin_connection(dsn)
    try:
        connection.execute(
            sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
        )
    finally:
        connection.close()


def postgres_metadata(dsn: str) -> dict[str, str]:
    validate_loopback_dsn(dsn)
    connection = _admin_connection(dsn)
    try:
        version = str(connection.execute("SHOW server_version").fetchone()["server_version"])
        isolation = str(
            connection.execute("SHOW default_transaction_isolation").fetchone()[
                "default_transaction_isolation"
            ]
        )
        return {"server_version": version, "transaction_isolation": isolation}
    finally:
        connection.close()


class PostgresIntegratedEffect:
    """Effect service using PostgreSQL row locks for transaction-bound commit."""

    def __init__(self, dsn: str, schema: str, authentication_key: bytes):
        require_psycopg()
        if len(authentication_key) < 16:
            raise ValueError("authentication key must contain at least 16 bytes")
        self.dsn = validate_loopback_dsn(dsn)
        self.schema = validate_schema_name(schema)
        self.authentication_key = authentication_key
        self.telemetry_lock = threading.Lock()
        self.telemetry: dict[str, dict[str, int | None]] = {}

        admin = _admin_connection(self.dsn)
        try:
            admin.execute(
                sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema))
            )
        finally:
            admin.close()

        connection = self._connect()
        try:
            statements = (
                """
                CREATE TABLE authorization_state (
                    trial_id TEXT PRIMARY KEY,
                    effect_json JSONB NOT NULL,
                    principal TEXT NOT NULL,
                    authorization_version BIGINT NOT NULL,
                    committed_at BIGINT NOT NULL,
                    confirmation_nonce TEXT,
                    nonce_consumed BOOLEAN NOT NULL,
                    state_revision BIGINT NOT NULL
                )
                """,
                """
                CREATE TABLE linearization_events (
                    sequence BIGSERIAL PRIMARY KEY,
                    trial_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    state_revision BIGINT NOT NULL
                )
                """,
                """
                CREATE TABLE effects (
                    trial_id TEXT PRIMARY KEY,
                    policy TEXT NOT NULL,
                    effect_json JSONB NOT NULL,
                    state_revision BIGINT NOT NULL,
                    linearization_sequence BIGINT NOT NULL
                        REFERENCES linearization_events(sequence)
                )
                """,
                """
                CREATE TABLE commit_attempts (
                    attempt_id BIGSERIAL PRIMARY KEY,
                    trial_id TEXT NOT NULL,
                    policy TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    state_revision BIGINT NOT NULL,
                    idempotent_replay BOOLEAN NOT NULL
                )
                """,
                """
                CREATE TABLE nonce_consumptions (
                    nonce TEXT PRIMARY KEY,
                    trial_id TEXT NOT NULL UNIQUE
                )
                """,
            )
            for statement in statements:
                connection.execute(statement)
            connection.commit()
        except Exception:
            connection.rollback()
            drop_postgres_schema(self.dsn, self.schema)
            raise
        finally:
            connection.close()

    def _connect(self) -> Any:
        return psycopg.connect(
            self.dsn,
            autocommit=False,
            row_factory=dict_row,
            options=f"-c search_path={self.schema}",
        )

    def _set_telemetry(self, trial_id: str, **values: int | None) -> None:
        with self.telemetry_lock:
            state = self.telemetry.setdefault(trial_id, {})
            state.update(values)

    def _telemetry(self, trial_id: str) -> dict[str, int | None]:
        with self.telemetry_lock:
            return dict(self.telemetry.get(trial_id, {}))

    @staticmethod
    def _context_from_row(row: dict[str, Any]) -> CommitContext:
        return CommitContext(
            principal=str(row["principal"]),
            authorization_version=int(row["authorization_version"]),
            committed_at=int(row["committed_at"]),
            confirmation_nonce=row["confirmation_nonce"],
            nonce_consumed=bool(row["nonce_consumed"]),
        )

    @staticmethod
    def _effect_from_row(row: dict[str, Any]) -> EffectSpec:
        payload = row["effect_json"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return EffectSpec(**payload)

    def dispatch(
        self, path: str, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        if path == "/health":
            return {
                "role": "postgres-integrated-effect",
                "backend": "postgresql",
                "pid": os.getpid(),
            }
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
        raise ValueError(f"unknown PostgreSQL effect route: {path}")

    def register(self, payload: dict[str, Any]) -> dict[str, Any]:
        trial_id = str(payload["trial_id"])
        effect = EffectSpec(**payload["effect"])
        context = CommitContext(**payload["context"])
        connection = self._connect()
        try:
            connection.execute(
                """
                INSERT INTO authorization_state
                    (trial_id, effect_json, principal, authorization_version,
                     committed_at, confirmation_nonce, nonce_consumed, state_revision)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
                """,
                (
                    trial_id,
                    Jsonb(effect.to_dict()),
                    context.principal,
                    context.authorization_version,
                    context.committed_at,
                    context.confirmation_nonce,
                    context.nonce_consumed,
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
                "SELECT * FROM authorization_state WHERE trial_id = %s", (trial_id,)
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
            current = connection.execute(
                """
                SELECT state_revision FROM authorization_state
                WHERE trial_id = %s FOR UPDATE
                """,
                (trial_id,),
            ).fetchone()
            acquired_ns = time.perf_counter_ns()
            self._set_telemetry(trial_id, mutation_lock_acquired_ns=acquired_ns)
            if current is None:
                raise ValueError(f"unknown trial: {trial_id}")
            revision = int(current["state_revision"]) + 1
            connection.execute(
                """
                UPDATE authorization_state
                SET effect_json = %s, principal = %s, authorization_version = %s,
                    committed_at = %s, confirmation_nonce = %s, nonce_consumed = %s,
                    state_revision = %s
                WHERE trial_id = %s
                """,
                (
                    Jsonb(effect.to_dict()),
                    context.principal,
                    context.authorization_version,
                    context.committed_at,
                    context.confirmation_nonce,
                    context.nonce_consumed,
                    revision,
                    trial_id,
                ),
            )
            sequence = int(
                connection.execute(
                    """
                    INSERT INTO linearization_events
                        (trial_id, event_type, state_revision)
                    VALUES (%s, %s, %s) RETURNING sequence
                    """,
                    (trial_id, "mutation", revision),
                ).fetchone()["sequence"]
            )
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

    def _counts(self, connection: Any, trial_id: str) -> dict[str, Any]:
        attempts = int(
            connection.execute(
                "SELECT COUNT(*) AS count FROM commit_attempts WHERE trial_id = %s",
                (trial_id,),
            ).fetchone()["count"]
        )
        effect = connection.execute(
            "SELECT linearization_sequence FROM effects WHERE trial_id = %s",
            (trial_id,),
        ).fetchone()
        mutation = connection.execute(
            """
            SELECT MAX(sequence) AS sequence FROM linearization_events
            WHERE trial_id = %s AND event_type = 'mutation'
            """,
            (trial_id,),
        ).fetchone()["sequence"]
        nonces = int(
            connection.execute(
                "SELECT COUNT(*) AS count FROM nonce_consumptions WHERE trial_id = %s",
                (trial_id,),
            ).fetchone()["count"]
        )
        return {
            "delivery_attempts": attempts,
            "effect_rows": int(effect is not None),
            "effect_sequence": int(effect["linearization_sequence"]) if effect else None,
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
        connection: Any,
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
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                trial_id,
                policy,
                decision,
                reason,
                state_revision,
                idempotent_replay,
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
            transaction_started_ns = time.perf_counter_ns()
            self._set_telemetry(
                trial_id, effect_transaction_started_ns=transaction_started_ns
            )
            state = connection.execute(
                """
                SELECT * FROM authorization_state
                WHERE trial_id = %s FOR UPDATE
                """,
                (trial_id,),
            ).fetchone()
            if state is None:
                raise ValueError(f"unknown trial: {trial_id}")
            revision = int(state["state_revision"])
            existing = connection.execute(
                "SELECT linearization_sequence FROM effects WHERE trial_id = %s",
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
                self._set_telemetry(trial_id, verification_completed_ns=verified_ns)
                if decision == "allow" and current_effect != commit_effect:
                    decision = "block"
                    reason = "authoritative effect differs from commit effect"
                if decision == "allow" and hold_ms:
                    time.sleep(hold_ms / 1000.0)
                if decision == "allow" and receipt.confirmation_nonce is not None:
                    nonce_row = connection.execute(
                        """
                        INSERT INTO nonce_consumptions (nonce, trial_id)
                        VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING nonce
                        """,
                        (receipt.confirmation_nonce, trial_id),
                    ).fetchone()
                    if nonce_row is None:
                        decision = "block"
                        reason = "confirmation nonce was already consumed"
                if decision == "allow":
                    sequence = int(
                        connection.execute(
                            """
                            INSERT INTO linearization_events
                                (trial_id, event_type, state_revision)
                            VALUES (%s, %s, %s) RETURNING sequence
                            """,
                            (trial_id, "effect_commit", revision),
                        ).fetchone()["sequence"]
                    )
                    connection.execute(
                        """
                        INSERT INTO effects
                            (trial_id, policy, effect_json, state_revision,
                             linearization_sequence)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            trial_id,
                            policy,
                            Jsonb(commit_effect.to_dict()),
                            revision,
                            sequence,
                        ),
                    )
                    if receipt.confirmation_nonce is not None:
                        connection.execute(
                            """
                            UPDATE authorization_state SET nonce_consumed = TRUE
                            WHERE trial_id = %s
                            """,
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
            state = connection.execute(
                """
                SELECT state_revision FROM authorization_state
                WHERE trial_id = %s FOR UPDATE
                """,
                (trial_id,),
            ).fetchone()
            if state is None:
                raise ValueError(f"unknown trial: {trial_id}")
            revision = int(state["state_revision"])
            existing = connection.execute(
                "SELECT linearization_sequence FROM effects WHERE trial_id = %s",
                (trial_id,),
            ).fetchone()
            if existing is None:
                sequence = int(
                    connection.execute(
                        """
                        INSERT INTO linearization_events
                            (trial_id, event_type, state_revision)
                        VALUES (%s, %s, %s) RETURNING sequence
                        """,
                        (trial_id, "effect_commit", revision),
                    ).fetchone()["sequence"]
                )
                connection.execute(
                    """
                    INSERT INTO effects
                        (trial_id, policy, effect_json, state_revision,
                         linearization_sequence)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        trial_id,
                        policy,
                        Jsonb(commit_effect.to_dict()),
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
