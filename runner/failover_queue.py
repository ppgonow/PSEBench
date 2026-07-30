"""Durable FIFO with explicit consumer ownership and failover recovery."""

from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import time
from typing import Any


class FailoverQueue:
    def __init__(self, database_path: pathlib.Path, *, busy_timeout_ms: int = 20_000):
        if busy_timeout_ms < 1:
            raise ValueError("busy timeout must be positive")
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path
        self.busy_timeout_ms = busy_timeout_ms
        connection = self._connect()
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    trial_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    owner TEXT
                );
                CREATE TABLE IF NOT EXISTS messages (
                    trial_id TEXT PRIMARY KEY,
                    message_json TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('queued', 'inflight', 'acked')),
                    enqueue_sequence INTEGER NOT NULL UNIQUE,
                    delivery_count INTEGER NOT NULL DEFAULT 0,
                    recovery_count INTEGER NOT NULL DEFAULT 0,
                    ack_count INTEGER NOT NULL DEFAULT 0,
                    substitution_count INTEGER NOT NULL DEFAULT 0,
                    owner TEXT
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
        )
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    @staticmethod
    def _begin(connection: sqlite3.Connection) -> None:
        connection.execute("BEGIN IMMEDIATE")

    @staticmethod
    def _event(
        connection: sqlite3.Connection,
        trial_id: str,
        event_type: str,
        owner: str | None,
    ) -> int:
        cursor = connection.execute(
            "INSERT INTO events (trial_id, event_type, owner) VALUES (?, ?, ?)",
            (trial_id, event_type, owner),
        )
        return int(cursor.lastrowid)

    def dispatch(
        self, path: str, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        if path == "/health":
            return {"role": "failover-broker", "pid": os.getpid()}
        if path == "/enqueue":
            return self.enqueue(payload)
        if path == "/substitute":
            return self.substitute(payload)
        if path == "/claim":
            return self.claim(str(payload["owner"]))
        if path == "/recover-owner":
            return self.recover_owner(str(payload["owner"]))
        if path == "/ack":
            return self.ack(str(payload["trial_id"]), str(payload["owner"]))
        if path == "/status":
            return self.status(str(payload["trial_id"]))
        if path == "/totals":
            return self.totals()
        raise ValueError(f"unknown failover queue route: {path}")

    def enqueue(self, payload: dict[str, Any]) -> dict[str, Any]:
        trial_id = str(payload["trial_id"])
        message = payload["message"]
        if not isinstance(message, dict):
            raise ValueError("message must be an object")
        connection = self._connect()
        try:
            self._begin(connection)
            sequence = self._event(connection, trial_id, "enqueue", None)
            connection.execute(
                "INSERT INTO messages VALUES (?, ?, 'queued', ?, 0, 0, 0, 0, NULL)",
                (trial_id, json.dumps(message, sort_keys=True), sequence),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {"service_pid": os.getpid(), "enqueue_sequence": sequence}

    def substitute(self, payload: dict[str, Any]) -> dict[str, Any]:
        trial_id = str(payload["trial_id"])
        message = payload["message"]
        if not isinstance(message, dict):
            raise ValueError("message must be an object")
        connection = self._connect()
        try:
            self._begin(connection)
            row = connection.execute(
                "SELECT state, delivery_count, substitution_count FROM messages WHERE trial_id = ?",
                (trial_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown trial: {trial_id}")
            if row["state"] != "queued" or int(row["delivery_count"]) != 0:
                raise ValueError("substitution requires an unclaimed message")
            if int(row["substitution_count"]):
                raise ValueError("message may be substituted at most once")
            connection.execute(
                "UPDATE messages SET message_json = ?, substitution_count = 1 WHERE trial_id = ?",
                (json.dumps(message, sort_keys=True), trial_id),
            )
            sequence = self._event(connection, trial_id, "substitute", None)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {"service_pid": os.getpid(), "substitution_sequence": sequence}

    def claim(self, owner: str) -> dict[str, Any]:
        if not owner or len(owner) > 64:
            raise ValueError("owner must contain 1-64 characters")
        connection = self._connect()
        try:
            self._begin(connection)
            row = connection.execute(
                """
                SELECT * FROM messages
                WHERE state = 'queued'
                ORDER BY enqueue_sequence
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                connection.commit()
                return {"service_pid": os.getpid(), "empty": 1}
            trial_id = str(row["trial_id"])
            delivery = int(row["delivery_count"]) + 1
            connection.execute(
                """
                UPDATE messages
                SET state = 'inflight', owner = ?, delivery_count = ?
                WHERE trial_id = ?
                """,
                (owner, delivery, trial_id),
            )
            sequence = self._event(connection, trial_id, "claim", owner)
            connection.commit()
            message = json.loads(str(row["message_json"]))
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {
            "service_pid": os.getpid(),
            "empty": 0,
            "trial_id": trial_id,
            "message": message,
            "delivery_number": delivery,
            "claim_sequence": sequence,
        }

    def recover_owner(self, owner: str) -> dict[str, Any]:
        connection = self._connect()
        recovered: list[str] = []
        try:
            self._begin(connection)
            rows = connection.execute(
                """
                SELECT trial_id FROM messages
                WHERE state = 'inflight' AND owner = ?
                ORDER BY enqueue_sequence
                """,
                (owner,),
            ).fetchall()
            for row in rows:
                trial_id = str(row["trial_id"])
                connection.execute(
                    """
                    UPDATE messages
                    SET state = 'queued', owner = NULL,
                        recovery_count = recovery_count + 1
                    WHERE trial_id = ?
                    """,
                    (trial_id,),
                )
                self._event(connection, trial_id, "recover", owner)
                recovered.append(trial_id)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {"service_pid": os.getpid(), "recovered": len(recovered)}

    def ack(self, trial_id: str, owner: str) -> dict[str, Any]:
        connection = self._connect()
        try:
            self._begin(connection)
            row = connection.execute(
                "SELECT state, owner, ack_count FROM messages WHERE trial_id = ?",
                (trial_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown trial: {trial_id}")
            if row["state"] != "inflight" or row["owner"] != owner:
                raise ValueError("ack requires the current inflight owner")
            if int(row["ack_count"]):
                raise ValueError("message may be acknowledged at most once")
            connection.execute(
                """
                UPDATE messages
                SET state = 'acked', owner = NULL, ack_count = 1
                WHERE trial_id = ?
                """,
                (trial_id,),
            )
            sequence = self._event(connection, trial_id, "ack", owner)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {"service_pid": os.getpid(), "ack_sequence": sequence}

    def status(self, trial_id: str) -> dict[str, Any]:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM messages WHERE trial_id = ?", (trial_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown trial: {trial_id}")
            return {
                "service_pid": os.getpid(),
                "state": str(row["state"]),
                "delivery_count": int(row["delivery_count"]),
                "recovery_count": int(row["recovery_count"]),
                "ack_count": int(row["ack_count"]),
                "substitution_count": int(row["substitution_count"]),
            }
        finally:
            connection.close()

    def totals(self) -> dict[str, Any]:
        connection = self._connect()
        try:
            aggregate = connection.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(delivery_count), 0),
                       COALESCE(SUM(recovery_count), 0),
                       COALESCE(SUM(ack_count), 0),
                       COALESCE(SUM(substitution_count), 0),
                       SUM(state = 'queued'), SUM(state = 'inflight'),
                       SUM(state = 'acked')
                FROM messages
                """
            ).fetchone()
            return {
                "service_pid": os.getpid(),
                "messages": int(aggregate[0]),
                "deliveries": int(aggregate[1]),
                "recoveries": int(aggregate[2]),
                "acks": int(aggregate[3]),
                "substitutions": int(aggregate[4]),
                "queued": int(aggregate[5] or 0),
                "inflight": int(aggregate[6] or 0),
                "acked": int(aggregate[7] or 0),
                "observed_ns": time.perf_counter_ns(),
            }
        finally:
            connection.close()
