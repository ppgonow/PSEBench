#!/usr/bin/env python3
"""Rerun the frozen factorial using Ollama JSON-schema constrained output."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
IN_DIR = ROOT / "tmp/local-authorization-factorial-20261010-v1"
OUT = ROOT / "tmp/local-authorization-factorial-20261010-v2b-structured"
MODEL = "qwen2.5:7b-instruct"
DIGEST = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["approve", "safe_fallback", "reason", "evidence"],
    "properties": {
        "approve": {"type": "boolean"},
        "safe_fallback": {"type": "boolean"},
        "reason": {"type": "string"},
        "evidence": {"type": "string"},
    },
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def api(path, payload):
    request = urllib.request.Request("http://127.0.0.1:11434" + path)
    if payload is not None:
        request.data = json.dumps(payload).encode()
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def check_model():
    models = api("/api/tags", None)["models"]
    if not any(m["name"] == MODEL and m["digest"] == DIGEST for m in models):
        raise ValueError("model digest changed or model absent")


def prepare():
    if OUT.exists():
        raise SystemExit(f"output exists: {OUT}")
    old_plan = json.loads((IN_DIR / "plan.json").read_text())
    old_plan_bytes = (IN_DIR / "plan.json").read_bytes()
    if old_plan["digest"] != DIGEST or len(old_plan["jobs"]) != 96:
        raise ValueError("unexpected v1 plan")
    OUT.mkdir()
    protocol = {
        "protocol_id": "local-authorization-factorial-20261010-v2b-structured",
        "status": "frozen_before_requests",
        "parent_plan_sha256": digest(old_plan_bytes),
        "model": MODEL,
        "model_digest": DIGEST,
        "jobs": old_plan["jobs"],
        "options": {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 256},
        "format_schema": SCHEMA,
        "stopping_rule": "one request per frozen job; retain every API and schema error; no replacement or adaptive retry",
        "analysis_boundary": "dependent development cases; descriptive only; no holdout, prevalence, or confirmatory framing claim",
        "runner_sha256": digest(Path(__file__).read_bytes()),
    }
    (OUT / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    print(json.dumps({"jobs": 96, "protocol_sha256": digest((OUT / "protocol.json").read_bytes()), "output": str(OUT)}))


def execute():
    protocol_bytes = (OUT / "protocol.json").read_bytes()
    protocol = json.loads(protocol_bytes)
    if protocol["runner_sha256"] != digest(Path(__file__).read_bytes()):
        raise ValueError("runner changed after freeze")
    check_model()
    with (OUT / "raw.jsonl").open("x") as handle:
        for index, job in enumerate(protocol["jobs"], 1):
            row = {key: value for key, value in job.items() if key != "prompt"}
            row.update({"protocol_sha256": digest(protocol_bytes), "response": None, "api_error": "", "schema_error": "", "decision": None})
            try:
                response = api("/api/chat", {"model": MODEL, "messages": [{"role": "user", "content": job["prompt"]}], "stream": False, "format": SCHEMA, "options": protocol["options"]})
                row["response"] = response
                content = response["message"]["content"]
                value = json.loads(content)
                if type(value.get("approve")) is not bool or type(value.get("safe_fallback")) is not bool or not all(isinstance(value.get(key), str) for key in ("reason", "evidence")) or set(value) != {"approve", "safe_fallback", "reason", "evidence"}:
                    raise ValueError("schema value mismatch")
                row["decision"] = value
            except Exception as error:
                if row["response"] is None:
                    row["api_error"] = str(error)
                else:
                    row["schema_error"] = str(error)
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            if index % 24 == 0:
                print(f"completed={index}/96", flush=True)
    check_model()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "execute"])
    args = parser.parse_args()
    prepare() if args.mode == "prepare" else execute()
