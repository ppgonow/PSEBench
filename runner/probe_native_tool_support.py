#!/usr/bin/env python3
"""Probe OpenAI-compatible native tool-call support without executing tools."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
from urllib.parse import urlparse

import requests


def redact(value: str, key: str) -> str:
    if key:
        value = value.replace(key, "<redacted-key>")
    value = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "<redacted-key>", value)
    return value[:500]


def probe(base_url: str, key: str, model: str, timeout: float) -> dict:
    response = requests.post(
        base_url.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Call record_probe_token exactly once. Do not answer with prose or JSON text.",
                },
                {"role": "user", "content": "Record token PSEBENCH_NATIVE_PROBE."},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "record_probe_token",
                        "description": "Record a synthetic protocol-test token.",
                        "parameters": {
                            "type": "object",
                            "properties": {"token": {"type": "string"}},
                            "required": ["token"],
                            "additionalProperties": False,
                        },
                    },
                }
            ],
            "tool_choice": "auto",
            "temperature": 0,
            "max_tokens": 128,
        },
        timeout=timeout,
    )
    try:
        data = response.json()
    except Exception as exc:
        raise RuntimeError(
            f"non-JSON response status={response.status_code} body={redact(response.text, key)!r}"
        ) from exc
    if response.status_code >= 400:
        raise RuntimeError(
            f"API status={response.status_code} error={redact(json.dumps(data), key)}"
        )
    message = ((data.get("choices") or [{}])[0].get("message") or {})
    calls = message.get("tool_calls") or []
    valid = []
    for call in calls:
        function = call.get("function") or {}
        arguments = function.get("arguments", "{}")
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        if function.get("name") == "record_probe_token" and isinstance(arguments, dict):
            valid.append(arguments)
    return {
        "model": model,
        "native_tool_calls": len(calls),
        "probe_tool_calls": len(valid),
        "protocol_pass": len(valid) == 1,
        "text_only_fallback": bool(message.get("content")) and not calls,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"))
    parser.add_argument("--models", nargs="+", default=["gpt-5.5", "grok-4.5"])
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    if not args.base_url:
        raise SystemExit("missing base URL: pass --base-url or set OPENAI_BASE_URL")
    parsed = urlparse(args.base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit("base URL must be HTTPS")
    key = os.environ.get("OPENAI_API_KEY") or getpass.getpass("API key: ")
    if not key:
        raise SystemExit("missing API key")
    results = []
    for model in args.models:
        try:
            result = probe(args.base_url, key, model, args.timeout)
        except Exception as exc:
            result = {
                "model": model,
                "native_tool_calls": 0,
                "probe_tool_calls": 0,
                "protocol_pass": False,
                "error": redact(str(exc), key),
            }
        results.append(result)
        print(json.dumps(result, sort_keys=True))
    if not all(result["protocol_pass"] for result in results):
        raise SystemExit("native tool-call protocol probe failed")


if __name__ == "__main__":
    main()
