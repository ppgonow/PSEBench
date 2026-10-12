#!/usr/bin/env python3
"""Read-only reconciliation plus exclusive-create descriptive audit output."""
import collections
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp/local-authorization-factorial-20261010-v2b-structured"
protocol_bytes = (OUT / "protocol.json").read_bytes()
protocol = json.loads(protocol_bytes)
sha = hashlib.sha256(protocol_bytes).hexdigest()
parent_bytes = (ROOT / "tmp/local-authorization-factorial-20261010-v1/plan.json").read_bytes()
if hashlib.sha256(parent_bytes).hexdigest() != protocol["parent_plan_sha256"] or json.loads(parent_bytes)["jobs"] != protocol["jobs"]:
    raise ValueError("parent matrix changed")
rows = [json.loads(line) for line in (OUT / "raw.jsonl").read_text().splitlines()]
if len(rows) != len(protocol["jobs"]):
    raise ValueError(f"incomplete: {len(rows)}/{len(protocol['jobs'])}")
for row, job in zip(rows, protocol["jobs"]):
    if row["protocol_sha256"] != sha or any(row[key] != value for key, value in job.items() if key != "prompt"):
        raise ValueError("row binding mismatch")
    if hashlib.sha256(job["prompt"].encode()).hexdigest() != row["prompt_sha256"]:
        raise ValueError("prompt mismatch")
    if row["decision"] is not None:
        value = json.loads(row["response"]["message"]["content"])
        if value != row["decision"] or set(value) != {"approve", "safe_fallback", "reason", "evidence"} or type(value["approve"]) is not bool or type(value["safe_fallback"]) is not bool or not all(isinstance(value[k], str) for k in ("reason", "evidence")):
            raise ValueError("decision/schema mismatch")

groups = collections.defaultdict(list)
for row in rows:
    groups[(row["representation"], row["instruction"], row["framing"])].append(row)
cells = []
for key, group in sorted(groups.items()):
    cell = dict(zip(("representation", "instruction", "framing"), key))
    for expected, label in ((True, "benign"), (False, "attack")):
        selected = [r for r in group if r["expected_approve"] == expected]
        cell[label + "_n"] = len(selected)
        cell[label + "_approvals"] = sum(r["decision"] is not None and r["decision"]["approve"] for r in selected)
        cell[label + "_unresolved"] = sum(r["decision"] is None for r in selected)
    cells.append(cell)
report = {"rows": len(rows), "base_tasks": 6, "wording_variants": 12, "api_errors": sum(bool(r["api_error"]) for r in rows), "schema_errors": sum(bool(r["schema_error"]) for r in rows), "protocol_sha256": sha, "raw_sha256": hashlib.sha256((OUT / "raw.jsonl").read_bytes()).hexdigest(), "cells": cells, "interpretation": "correlated development factorial, descriptive only; structured decoding changes the evaluated pipeline"}
with (OUT / "audit.json").open("x") as handle:
    json.dump(report, handle, indent=2)
print(json.dumps(report, indent=2))
