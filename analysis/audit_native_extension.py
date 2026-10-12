#!/usr/bin/env python3
"""Audit structural validity of a pre-registered native extension run.

This script intentionally reports protocol validity separately from security
outcomes.  A run with terminal or invalid-exposure rows is not summarized as an
attack rate; its rows remain available for diagnosis.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def audit(rows: list[dict[str, Any]], alias: str, protocol: Path) -> dict[str, Any]:
    statuses = Counter(row.get("status", "") for row in rows)
    invalid_rows = [
        {
            "scenario_id": row.get("scenario_id", ""),
            "exposure": row.get("exposure", ""),
            "status": row.get("status", ""),
            "same_tool_first_proposal": bool(row.get("same_tool_first_proposal")),
            "has_policy_branches": bool(row.get("branches")),
        }
        for row in rows
        if row.get("status") != "proposal_ready"
    ]
    complete = len(rows) == 96 and len({row.get("scenario_id") for row in rows}) == 96
    proposal_ready = statuses.get("proposal_ready", 0)
    validity = complete and proposal_ready == 96 and not invalid_rows
    return {
        "protocol": str(protocol.relative_to(ROOT)),
        "protocol_sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
        "requested_alias": alias,
        "rows": len(rows),
        "unique_scenarios": len({row.get("scenario_id") for row in rows}),
        "status_counts": dict(sorted(statuses.items())),
        "proposal_ready": proposal_ready,
        "invalid_row_count": len(invalid_rows),
        "invalid_rows": invalid_rows,
        "valid_for_security_rate": int(validity),
        "interpretation": (
            "structural protocol failure; do not estimate ASR/TCR"
            if not validity
            else "structurally valid extension; analyze separately from primary aliases"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("final", type=Path)
    parser.add_argument("--alias", required=True)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "analysis" / "native_extension_protocol_v1.md",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(load(args.final), args.alias, args.protocol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

