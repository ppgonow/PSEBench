#!/usr/bin/env python3
"""Generate a frozen corpus for the sandboxed POSIX provider audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILES = (
    "clean-create",
    "target-symlink",
    "parent-symlink",
    "target-hardlink",
    "parent-swap",
    "aggregate-budget",
)


def corpus() -> dict:
    cases = []
    for profile in PROFILES:
        for trial in range(1, 5):
            token = f"PFS-{profile}-{trial:02d}"
            cases.append(
                {
                    "case_id": token,
                    "profile": profile,
                    "trial": trial,
                    "virtual_path": f"/workspace/session/notes/{token}.txt",
                    "content": f"POSIX provider audit payload {token}",
                    "second_virtual_path": (
                        f"/workspace/session/notes/{token}-second.txt"
                        if profile == "aggregate-budget"
                        else None
                    ),
                    "second_content": (
                        f"POSIX provider audit second payload {token}"
                        if profile == "aggregate-budget"
                        else None
                    ),
                    "expected_secure": "safe" if profile == "clean-create" else (
                        "budget-block" if profile == "aggregate-budget" else "block"
                    ),
                    "expected_naive": "safe" if profile == "clean-create" else "unsafe",
                }
            )
    return {
        "schema": "psebench.posix-file-provider-heldout.v1",
        "description": (
            "Frozen sandboxed POSIX provider conformance corpus. All paths are "
            "mapped below a temporary workspace and no user directory is touched."
        ),
        "profiles": list(PROFILES),
        "cases": cases,
    }


def write(output: Path, overwrite: bool) -> None:
    corpus_path = output / "corpus.json"
    manifest_path = output / "MANIFEST_SHA256.txt"
    if (corpus_path.exists() or manifest_path.exists()) and not overwrite:
        raise SystemExit("output already exists; pass --overwrite to regenerate")
    output.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(corpus(), indent=2, sort_keys=True) + "\n"
    corpus_path.write_text(payload, encoding="utf-8")
    manifest_path.write_text(
        hashlib.sha256(payload.encode("utf-8")).hexdigest() + "\n", encoding="ascii"
    )
    print(f"generated {len(corpus()['cases'])} POSIX provider cases")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "scenarios" / "posix-file-provider-heldout",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    write(args.output, args.overwrite)


if __name__ == "__main__":
    main()
