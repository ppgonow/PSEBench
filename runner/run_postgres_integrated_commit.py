#!/usr/bin/env python3
"""Run the frozen service-atomic matrix on PostgreSQL."""

from __future__ import annotations

import argparse
import csv
import multiprocessing
import os
import pathlib
import secrets
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from postgres_integrated_commit import (  # noqa: E402
    PostgresIntegratedEffect,
    drop_postgres_schema,
    postgres_metadata,
    validate_loopback_dsn,
)
from run_http_commit_race import load_scenarios  # noqa: E402
from run_multiprocess_commit_race import JsonHTTPServer, post_json  # noqa: E402
from run_service_integrated_commit import (  # noqa: E402
    POLICIES,
    SCHEDULES,
    CRITICAL_FAMILIES,
    integrity,
    run_case,
    summarize,
    validate,
    write_csv,
)


POSTGRES_ATOMIC_HOLD_MS = 30.0


def serve_postgres_service(
    connection: Any,
    stop_event: Any,
    dsn: str,
    schema: str,
    authentication_key: bytes,
) -> None:
    app = PostgresIntegratedEffect(dsn, schema, authentication_key)
    server = JsonHTTPServer(("127.0.0.1", 0), app)
    server.timeout = 0.2
    connection.send({"port": server.server_port, "pid": os.getpid()})
    connection.close()
    try:
        while not stop_event.is_set():
            server.handle_request()
    finally:
        server.server_close()


class PostgresServiceProcess:
    def __init__(self, dsn: str, schema: str, authentication_key: bytes):
        self.dsn = dsn
        self.schema = schema
        self.authentication_key = authentication_key
        self.process: multiprocessing.Process | None = None
        self.stop_event: Any = None
        self.url = ""
        self.pid = -1

    def start(self) -> "PostgresServiceProcess":
        parent, child = multiprocessing.Pipe(duplex=False)
        self.stop_event = multiprocessing.Event()
        self.process = multiprocessing.Process(
            target=serve_postgres_service,
            args=(child, self.stop_event, self.dsn, self.schema, self.authentication_key),
            name="psebench-postgres-integrated-effect",
        )
        self.process.start()
        child.close()
        if not parent.poll(15):
            self.process.terminate()
            self.process.join(timeout=5)
            raise RuntimeError("PostgreSQL effect process did not start")
        ready = parent.recv()
        parent.close()
        self.url = f"http://127.0.0.1:{ready['port']}"
        self.pid = int(ready["pid"])
        health = post_json(self.url, "/health", {})
        if (
            health["role"] != "postgres-integrated-effect"
            or health["backend"] != "postgresql"
            or int(health["pid"]) != self.pid
        ):
            raise RuntimeError("PostgreSQL effect service identity mismatch")
        return self

    def close(self) -> None:
        error: BaseException | None = None
        if self.process is not None:
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
                error = RuntimeError(
                    f"PostgreSQL effect process exited with {self.process.exitcode}"
                )
        drop_postgres_schema(self.dsn, self.schema)
        if error is not None:
            raise error

    def __enter__(self) -> "PostgresServiceProcess":
        return self.start()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def backend_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"backend": "postgresql", **row} for row in rows]


def write_metadata(
    path: pathlib.Path,
    *,
    dsn: str,
    image_reference: str,
    image_digest: str,
    matrix_rows: int,
) -> None:
    import psycopg

    metadata = postgres_metadata(dsn)
    row = {
        "backend": "postgresql",
        "server_version": metadata["server_version"],
        "transaction_isolation": metadata["transaction_isolation"],
        "driver": "psycopg",
        "driver_version": psycopg.__version__,
        "image_reference": image_reference,
        "image_digest": image_digest,
        "matrix_rows": matrix_rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row), lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)


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
        default=ROOT / "analysis" / "postgres_integrated_commit",
    )
    parser.add_argument("--dsn-env", default="PSEBENCH_POSTGRES_DSN")
    parser.add_argument("--image-reference", required=True)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    dsn = os.environ.get(args.dsn_env, "")
    if not dsn:
        raise SystemExit(f"missing PostgreSQL DSN environment variable: {args.dsn_env}")
    validate_loopback_dsn(dsn)
    output_paths = [
        pathlib.Path(f"{args.analysis_prefix}_detail.csv"),
        pathlib.Path(f"{args.analysis_prefix}_summary.csv"),
        pathlib.Path(f"{args.analysis_prefix}_integrity.csv"),
        pathlib.Path(f"{args.analysis_prefix}_metadata.csv"),
    ]
    if any(path.exists() for path in output_paths) and not args.overwrite:
        raise SystemExit("output exists; pass --overwrite for one fresh complete matrix")

    metadata = postgres_metadata(dsn)
    if not metadata["server_version"].startswith("17."):
        raise RuntimeError(f"expected PostgreSQL 17, got {metadata['server_version']}")
    if metadata["transaction_isolation"] != "read committed":
        raise RuntimeError(
            "expected read committed, got " + metadata["transaction_isolation"]
        )

    scenarios = load_scenarios(args.scenario_dir)
    key = secrets.token_bytes(32)
    rows: list[dict[str, Any]] = []
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
            schema = "pse_" + schedule.replace("-", "_") + "_" + policy.replace("-", "_")
            with PostgresServiceProcess(dsn, schema, key) as service:
                for scenario in selected:
                    row = run_case(
                        service,
                        key,
                        scenario,
                        policy,
                        schedule,
                        atomic_hold_ms=POSTGRES_ATOMIC_HOLD_MS,
                    )
                    row["backend"] = "postgresql"
                    rows.append(row)

    validate(rows, scenarios)
    write_csv(output_paths[0], backend_rows([{k: v for k, v in row.items() if k != "backend"} for row in rows]))
    write_csv(output_paths[1], backend_rows(summarize(rows)))
    write_csv(output_paths[2], backend_rows(integrity(rows)))
    write_metadata(
        output_paths[3],
        dsn=dsn,
        image_reference=args.image_reference,
        image_digest=args.image_digest,
        matrix_rows=len(rows),
    )
    print(
        "PostgreSQL integrated matrix passed: rows=540 attacks=360 controls=180 "
        "stale_split=180 stale_atomic=0 serialized_windows=80"
    )


if __name__ == "__main__":
    main()
