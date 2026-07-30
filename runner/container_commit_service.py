#!/usr/bin/env python3
"""Run one commit-race service inside an isolated container."""

from __future__ import annotations

import argparse
import pathlib
from typing import Any

from run_multiprocess_commit_race import (
    AuthorizationService,
    CommitGateway,
    EffectService,
    JsonHTTPServer,
)


INSTANCE_IDS = {
    "authorization": 101,
    "gateway": 102,
    "effect": 103,
}


def read_authentication_key(path: pathlib.Path) -> bytes:
    try:
        key = bytes.fromhex(path.read_text(encoding="ascii").strip())
    except (OSError, ValueError) as exc:
        raise ValueError("authentication key file must contain hexadecimal bytes") from exc
    if len(key) != 32:
        raise ValueError("authentication key must contain exactly 32 bytes")
    return key


class ContainerIdentityApp:
    """Expose logical identities because each container may use the same PID."""

    def __init__(self, role: str, app: Any):
        self.role = role
        self.app = app
        self.instance_id = INSTANCE_IDS[role]

    def dispatch(
        self, path: str, payload: dict[str, Any], request_received_ns: int
    ) -> dict[str, Any]:
        result = self.app.dispatch(path, payload, request_received_ns)
        if path == "/health":
            return {
                "role": self.role,
                "service_instance_id": self.instance_id,
            }
        if self.role in {"authorization", "effect"} and "service_pid" in result:
            result["service_pid"] = self.instance_id
        if self.role == "gateway" and "gateway_pid" in result:
            result["gateway_pid"] = self.instance_id
        return result

    def close(self) -> None:
        close = getattr(self.app, "close", None)
        if close is not None:
            close()


def build_app(args: argparse.Namespace) -> ContainerIdentityApp:
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
    return ContainerIdentityApp(args.role, app)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=tuple(INSTANCE_IDS))
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--authentication-key-file",
        type=pathlib.Path,
        default=pathlib.Path("/run/secrets/commit_hmac"),
    )
    parser.add_argument("--authorization-url", default="http://authorization:8080")
    parser.add_argument("--effect-url", default="http://effect:8080")
    parser.add_argument(
        "--database-path",
        type=pathlib.Path,
        default=pathlib.Path("/data/service.sqlite"),
    )
    parser.add_argument("--state-delay-ms", type=float, default=0.5)
    parser.add_argument("--service-delay-ms", type=float, default=0.5)
    args = parser.parse_args()
    if not 0 < args.port < 65536:
        raise SystemExit("port must be between 1 and 65535")
    if args.state_delay_ms < 0 or args.service_delay_ms < 0:
        raise SystemExit("service delays must be non-negative")

    app = build_app(args)
    server = JsonHTTPServer((args.bind, args.port), app)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        app.close()


if __name__ == "__main__":
    main()
