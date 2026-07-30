#!/usr/bin/env python3
"""Consumer worker commands executed inside isolated Docker containers."""

from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any
from urllib.request import Request, urlopen


def post_json(base_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    request = Request(
        base_url + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        result = json.loads(response.read())
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result


def commit(effect_url: str, message: dict[str, Any]) -> dict[str, Any]:
    policy = str(message["effect_policy"])
    endpoint = "/commit-unverified" if policy == "gateway-split" else "/commit-atomic"
    return post_json(
        effect_url,
        endpoint,
        {
            "trial_id": message["trial_id"],
            "policy": policy,
            "receipt": message["receipt"],
            "commit_effect": message["commit_effect"],
        },
    )


def write_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def claim_batch(args: argparse.Namespace) -> None:
    claims: list[dict[str, Any]] = []
    for _ in range(args.count):
        claim = post_json(args.broker_url, "/claim", {"owner": args.owner})
        if claim.get("empty"):
            raise RuntimeError("broker emptied before requested claim count")
        claims.append(claim)
    write_json(args.state_file, claims)
    print(json.dumps({"claimed": len(claims)}, sort_keys=True))


def commit_held(args: argparse.Namespace) -> None:
    claims = json.loads(args.state_file.read_text(encoding="utf-8"))
    results = [commit(args.effect_url, claim["message"]) for claim in claims]
    write_json(args.result_file, results)
    print(json.dumps({"committed_attempts": len(results)}, sort_keys=True))


def process_batch(args: argparse.Namespace) -> None:
    results: list[dict[str, Any]] = []
    for _ in range(args.count):
        claim = post_json(args.broker_url, "/claim", {"owner": args.owner})
        if claim.get("empty"):
            raise RuntimeError("broker emptied before failover count")
        outcome = commit(args.effect_url, claim["message"])
        post_json(
            args.broker_url,
            "/ack",
            {"trial_id": claim["trial_id"], "owner": args.owner},
        )
        results.append(
            {
                "trial_id": claim["trial_id"],
                "delivery_number": claim["delivery_number"],
                "decision": outcome["decision"],
                "idempotent_replay": outcome["idempotent_replay"],
            }
        )
    write_json(args.result_file, results)
    print(json.dumps({"processed": len(results)}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    claim = subparsers.add_parser("claim-batch")
    claim.add_argument("--broker-url", required=True)
    claim.add_argument("--owner", required=True)
    claim.add_argument("--count", type=int, required=True)
    claim.add_argument("--state-file", type=pathlib.Path, required=True)
    claim.set_defaults(func=claim_batch)

    held = subparsers.add_parser("commit-held")
    held.add_argument("--effect-url", required=True)
    held.add_argument("--state-file", type=pathlib.Path, required=True)
    held.add_argument("--result-file", type=pathlib.Path, required=True)
    held.set_defaults(func=commit_held)

    process = subparsers.add_parser("process-batch")
    process.add_argument("--broker-url", required=True)
    process.add_argument("--effect-url", required=True)
    process.add_argument("--owner", required=True)
    process.add_argument("--count", type=int, required=True)
    process.add_argument("--result-file", type=pathlib.Path, required=True)
    process.set_defaults(func=process_batch)

    args = parser.parse_args()
    if getattr(args, "count", 1) < 1:
        raise SystemExit("count must be positive")
    args.func(args)


if __name__ == "__main__":
    main()
