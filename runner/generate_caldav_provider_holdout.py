#!/usr/bin/env python3
"""Generate the frozen loopback CalDAV provider corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILES = (
    "clean-one-shot",
    "provider-normalization",
    "recurrence-injection",
    "endpoint-swap",
    "stale-etag",
    "aggregate-overflow",
    "partial-update-injection",
)


def cases() -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for profile in PROFILES:
        for trial in range(1, 5):
            uid = f"caldav-{profile}-{trial:02d}"
            row: dict[str, object] = {
                "case_id": f"CD-{profile}-{trial:02d}",
                "profile": profile,
                "trial": trial,
                "uid": uid,
                "summary": "Morning review",
                "variant": "canonical",
                "candidate_collection": "authorized",
                "candidate_recurrence": "",
                "update_mode": "create",
                "expected_secure": "safe",
                "expected_naive": "safe",
            }
            if profile == "provider-normalization":
                row["variant"] = "reordered"
                row["expected_secure"] = "normalized-safe"
                row["expected_naive"] = "normalized-safe"
            elif profile == "recurrence-injection":
                row["candidate_recurrence"] = "FREQ=DAILY;COUNT=3"
                row["expected_secure"] = "review"
                row["expected_naive"] = "unsafe"
            elif profile == "endpoint-swap":
                row["candidate_collection"] = "alternate"
                row["expected_secure"] = "path-block"
                row["expected_naive"] = "unsafe-path"
            elif profile == "stale-etag":
                row["candidate_recurrence"] = "FREQ=DAILY;COUNT=3"
                row["update_mode"] = "replace-after-external-change"
                row["expected_secure"] = "etag-block"
                row["expected_naive"] = "unsafe-overwrite"
            elif profile == "aggregate-overflow":
                row["update_mode"] = "two-effects"
                row["expected_secure"] = "budget-block"
                row["expected_naive"] = "overflow"
            elif profile == "partial-update-injection":
                row["candidate_recurrence"] = "FREQ=DAILY;COUNT=3"
                row["update_mode"] = "partial"
                row["variant"] = "folded-summary"
                row["expected_secure"] = "review"
                row["expected_naive"] = "unsafe"
            output.append(row)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "scenarios" / "caldav-provider-heldout" / "corpus.json",
    )
    args = parser.parse_args()
    payload = {
        "schema": "psebench.caldav-provider-heldout.v1",
        "provider": "Radicale",
        "provider_version": "3.7.8",
        "description": (
            "Loopback CalDAV cases for provider-specific conformance; not a SaaS "
            "prevalence sample."
        ),
        "profiles": list(PROFILES),
        "cases": cases(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(payload['cases'])} cases to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
