#!/usr/bin/env python3
"""Serve one commit-race role on a remote loopback interface."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
from typing import Any

from run_multiprocess_commit_race import (
    AuthorizationService,
    CommitGateway,
    EffectService,
    JsonHTTPServer,
    post_json,
)


INSTANCE_IDS = {
    "authorization": 201,
    "gateway": 202,
    "effect": 203,
}


def read_authentication_key(path: pathlib.Path) -> bytes:
    try:
        key = bytes.fromhex(path.read_text(encoding="ascii").strip())
    except (OSError, ValueError) as exc:
        raise ValueError("authentication key file must contain hexadecimal bytes") from exc
    if len(key) != 32:
        raise ValueError("authentication key must contain exactly 32 bytes")
    return key


class MultiHostIdentityApp:
    """Replace process IDs with stable, non-identifying logical role IDs."""

    def __init__(self, role: str, app: Any):
        self.role = role
        self.app = app
        self.instance_id = INSTANCE_IDS[role]

    def dispatch(
        self, path: str, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        if path == "/health":
            return {
                "role": self.role,
                "service_instance_id": self.instance_id,
            }
        if path == "/downstream-health" and self.role == "gateway":
            authorization = post_json(self.app.authorization_url, "/health", {})
            effect = post_json(self.app.effect_url, "/health", {})
            return {
                "authorization_role": authorization.get("role"),
                "authorization_instance_id": authorization.get(
                    "service_instance_id"
                ),
                "effect_role": effect.get("role"),
                "effect_instance_id": effect.get("service_instance_id"),
            }

        result = self.app.dispatch(path, payload, request_received_ns)
        if self.role in {"authorization", "effect"} and "service_pid" in result:
            result["service_pid"] = self.instance_id
        if self.role == "gateway" and "gateway_pid" in result:
            result["gateway_pid"] = self.instance_id
        return result

    def close(self) -> None:
        close = getattr(self.app, "close", None)
        if close is not None:
            close()


def build_app(args: argparse.Namespace) -> MultiHostIdentityApp:
    if args.role == "authorization":
        app: Any = AuthorizationService(
            read_authentication_key(args.authentication_key_file),
            args.state_delay_ms,
        )
    elif args.role == "gateway":
        app = CommitGateway(
            args.authorization_url,
            args.effect_url,
            read_authentication_key(args.authentication_key_file),
        )
    else:
        app = EffectService(args.database_path, args.service_delay_ms)
    return MultiHostIdentityApp(args.role, app)


def write_ready(path: pathlib.Path, role: str, port: int) -> None:
    payload = {
        "role": role,
        "service_instance_id": INSTANCE_IDS[role],
        "port": port,
        "bind_scope": "loopback",
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=tuple(INSTANCE_IDS))
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--ready-file", type=pathlib.Path, required=True)
    parser.add_argument(
        "--authentication-key-file",
        type=pathlib.Path,
        default=pathlib.Path("runtime/commit_hmac"),
    )
    parser.add_argument("--authorization-url")
    parser.add_argument("--effect-url")
    parser.add_argument(
        "--database-path",
        type=pathlib.Path,
        default=pathlib.Path("runtime/service.sqlite"),
    )
    parser.add_argument("--state-delay-ms", type=float, default=0.5)
    parser.add_argument("--service-delay-ms", type=float, default=0.5)
    args = parser.parse_args()
    if not 0 <= args.port < 65536:
        raise SystemExit("port must be between 0 and 65535")
    if args.state_delay_ms < 0 or args.service_delay_ms < 0:
        raise SystemExit("service delays must be non-negative")
    if args.role == "gateway" and not (
        args.authorization_url and args.effect_url
    ):
        raise SystemExit("gateway requires authorization and effect URLs")
    if args.ready_file.exists():
        raise SystemExit("ready file already exists")

    app = build_app(args)
    server = JsonHTTPServer(("127.0.0.1", args.port), app)
    write_ready(args.ready_file, args.role, server.server_port)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        app.close()


if __name__ == "__main__":
    main()
