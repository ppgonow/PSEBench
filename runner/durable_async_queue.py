"""Loopback-only durable queue used by the asynchronous commit experiment."""

from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import time
from typing import Any


class DurableAsyncQueue:
    """Small SQLite-backed FIFO with explicit at-least-once redelivery."""

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
                CREATE TABLE IF NOT EXISTS queue_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    trial_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    delivery_number INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    trial_id TEXT PRIMARY KEY,
                    message_json TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('queued', 'inflight', 'acked')),
                    enqueue_sequence INTEGER NOT NULL UNIQUE,
                    delivery_count INTEGER NOT NULL DEFAULT 0,
                    release_count INTEGER NOT NULL DEFAULT 0,
                    ack_count INTEGER NOT NULL DEFAULT 0,
                    substitution_count INTEGER NOT NULL DEFAULT 0
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
    def _insert_event(
        connection: sqlite3.Connection,
        trial_id: str,
        event_type: str,
        delivery_number: int,
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO queue_events (trial_id, event_type, delivery_number)
            VALUES (?, ?, ?)
            """,
            (trial_id, event_type, delivery_number),
        )
        return int(cursor.lastrowid)

    def dispatch(
        self, path: str, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        if path == "/health":
            return {"role": "durable-async-broker", "pid": os.getpid()}
        if path == "/enqueue":
            return self.enqueue(payload, request_received_ns)
        if path == "/substitute":
            return self.substitute(payload, request_received_ns)
        if path == "/claim":
            return self.claim(request_received_ns)
        if path == "/release":
            return self.release(payload, request_received_ns)
        if path == "/ack":
            return self.ack(payload, request_received_ns)
        if path == "/status":
            return self.status(str(payload["trial_id"]))
        if path == "/totals":
            return self.totals()
        raise ValueError(f"unknown durable queue route: {path}")

    def enqueue(
        self, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        trial_id = str(payload["trial_id"])
        message = payload["message"]
        if not isinstance(message, dict):
            raise ValueError("message must be an object")
        connection = self._connect()
        try:
            self._begin(connection)
            sequence = self._insert_event(connection, trial_id, "enqueue", 0)
            connection.execute(
                "INSERT INTO messages VALUES (?, ?, 'queued', ?, 0, 0, 0, 0)",
                (trial_id, json.dumps(message, sort_keys=True), sequence),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {
            "service_pid": os.getpid(),
            "trial_id": trial_id,
            "enqueue_sequence": sequence,
            "request_received_ns": request_received_ns,
        }

    def substitute(
        self, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
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
                raise ValueError("message substitution is allowed only before first claim")
            if int(row["substitution_count"]) != 0:
                raise ValueError("message may be substituted at most once")
            connection.execute(
                "UPDATE messages SET message_json = ?, substitution_count = 1 WHERE trial_id = ?",
                (json.dumps(message, sort_keys=True), trial_id),
            )
            sequence = self._insert_event(connection, trial_id, "substitute", 0)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {
            "service_pid": os.getpid(),
            "trial_id": trial_id,
            "substitution_sequence": sequence,
            "request_received_ns": request_received_ns,
        }

    def claim(self, request_received_ns: int) -> dict[str, Any]:
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
            delivery_number = int(row["delivery_count"]) + 1
            connection.execute(
                "UPDATE messages SET state = 'inflight', delivery_count = ? WHERE trial_id = ?",
                (delivery_number, trial_id),
            )
            sequence = self._insert_event(
                connection, trial_id, "claim", delivery_number
            )
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
            "enqueue_sequence": int(row["enqueue_sequence"]),
            "delivery_number": delivery_number,
            "claim_sequence": sequence,
            "request_received_ns": request_received_ns,
        }

    def release(
        self, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        trial_id = str(payload["trial_id"])
        connection = self._connect()
        try:
            self._begin(connection)
            row = connection.execute(
                "SELECT state, delivery_count, release_count FROM messages WHERE trial_id = ?",
                (trial_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown trial: {trial_id}")
            if row["state"] != "inflight":
                raise ValueError("only an inflight message can be released")
            release_count = int(row["release_count"]) + 1
            connection.execute(
                "UPDATE messages SET state = 'queued', release_count = ? WHERE trial_id = ?",
                (release_count, trial_id),
            )
            sequence = self._insert_event(
                connection, trial_id, "release", int(row["delivery_count"])
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {
            "service_pid": os.getpid(),
            "trial_id": trial_id,
            "release_count": release_count,
            "release_sequence": sequence,
            "request_received_ns": request_received_ns,
        }

    def ack(
        self, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        trial_id = str(payload["trial_id"])
        connection = self._connect()
        try:
            self._begin(connection)
            row = connection.execute(
                "SELECT state, delivery_count, ack_count FROM messages WHERE trial_id = ?",
                (trial_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown trial: {trial_id}")
            if row["state"] != "inflight":
                raise ValueError("only an inflight message can be acknowledged")
            if int(row["ack_count"]) != 0:
                raise ValueError("message may be acknowledged at most once")
            connection.execute(
                "UPDATE messages SET state = 'acked', ack_count = 1 WHERE trial_id = ?",
                (trial_id,),
            )
            sequence = self._insert_event(
                connection, trial_id, "ack", int(row["delivery_count"])
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return {
            "service_pid": os.getpid(),
            "trial_id": trial_id,
            "ack_count": 1,
            "ack_sequence": sequence,
            "request_received_ns": request_received_ns,
        }

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
                "trial_id": trial_id,
                "state": str(row["state"]),
                "enqueue_sequence": int(row["enqueue_sequence"]),
                "delivery_count": int(row["delivery_count"]),
                "release_count": int(row["release_count"]),
                "ack_count": int(row["ack_count"]),
                "substitution_count": int(row["substitution_count"]),
            }
        finally:
            connection.close()

    def totals(self) -> dict[str, Any]:
        connection = self._connect()
        try:
            values = {
                state: int(
                    connection.execute(
                        "SELECT COUNT(*) FROM messages WHERE state = ?", (state,)
                    ).fetchone()[0]
                )
                for state in ("queued", "inflight", "acked")
            }
            aggregate = connection.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(delivery_count), 0),
                       COALESCE(SUM(release_count), 0), COALESCE(SUM(ack_count), 0),
                       COALESCE(SUM(substitution_count), 0)
                FROM messages
                """
            ).fetchone()
            return {
                "service_pid": os.getpid(),
                "messages": int(aggregate[0]),
                "deliveries": int(aggregate[1]),
                "releases": int(aggregate[2]),
                "acks": int(aggregate[3]),
                "substitutions": int(aggregate[4]),
                **values,
                "observed_ns": time.perf_counter_ns(),
            }
        finally:
            connection.close()
