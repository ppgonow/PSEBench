#!/usr/bin/env python3
"""Container entry point for the Docker queue-failover experiment."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import pathlib
import time
from typing import Any

from failover_queue import FailoverQueue
from service_integrated_commit import ServiceIntegratedEffect


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            result = self.server.app.dispatch(  # type: ignore[attr-defined]
                self.path, payload, time.perf_counter_ns()
            )
            body = json.dumps(result, sort_keys=True).encode("utf-8")
            status = 200
        except Exception as exc:
            body = json.dumps({"error": str(exc)}, sort_keys=True).encode("utf-8")
            status = 400
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


class JsonHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], app: Any):
        self.app = app
        super().__init__(address, Handler)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=("broker", "effect"))
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--database-path", type=pathlib.Path, required=True)
    parser.add_argument("--authentication-key-file", type=pathlib.Path)
    args = parser.parse_args()
    if not 0 < args.port < 65536:
        raise SystemExit("port must be between 1 and 65535")
    if args.role == "broker":
        app = FailoverQueue(args.database_path)
    else:
        if args.authentication_key_file is None:
            raise SystemExit("effect role requires --authentication-key-file")
        key = args.authentication_key_file.read_bytes()
        app = ServiceIntegratedEffect(args.database_path, key)
    server = JsonHTTPServer((args.bind, args.port), app)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
