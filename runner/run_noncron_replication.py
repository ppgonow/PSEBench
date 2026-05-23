#!/usr/bin/env python3
"""Run the final local non-cron replication slice.

The script creates the `riskfix2-*` artifacts used by the paper appendix. It
uses `--no-notify`, so it does not require live message-delivery credentials.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ["python3", "runner/run_hybrid_cli.py"]
CHAT_ID = "LOCAL_NO_NOTIFY"


def add(specs: list[list[str]], scenario: Path, tag: str, extra: list[str]) -> None:
    specs.append(
        [
            *RUNNER,
            str(scenario.relative_to(ROOT)),
            "--run-id",
            "riskfix2",
            "--tag",
            tag,
            "--chat-id",
            CHAT_ID,
            "--no-notify",
            *extra,
        ]
    )


def main() -> None:
    specs: list[list[str]] = []

    for scenario in sorted((ROOT / "scenarios/hybrid-file").glob("H-file-persist-required-*.yaml")):
        add(specs, scenario, "noncron-file-permissive", ["--allow-injected"])
        add(specs, scenario, "noncron-file-iacg", [])

    for scenario in sorted((ROOT / "scenarios/hybrid-calendar").glob("H-calendar-recurring-required-*.yaml")):
        add(specs, scenario, "noncron-calendar-permissive", ["--allow-injected"])
        add(specs, scenario, "noncron-calendar-iacg", [])

    for scenario in sorted((ROOT / "scenarios/hybrid-msg").glob("H-msg-msg-required-*.yaml")):
        add(specs, scenario, "noncron-recipient-permissive", ["--allow-injected"])
        add(specs, scenario, "noncron-recipient-iacg", [])

    for scenario in sorted((ROOT / "scenarios/hybrid-file").glob("H-file-persist-legit-*.yaml")):
        add(specs, scenario, "noncron-file-legit-iacg", [])
        add(specs, scenario, "noncron-file-legit-firewall", ["--firewall"])

    for scenario in sorted((ROOT / "scenarios/hybrid-calendar").glob("H-calendar-recurring-legit-*.yaml")):
        add(specs, scenario, "noncron-calendar-legit-iacg", [])
        add(specs, scenario, "noncron-calendar-legit-firewall", ["--firewall"])

    failures: list[tuple[list[str], int, str, str]] = []
    for cmd in specs:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=60)
        if proc.returncode != 0:
            failures.append((cmd, proc.returncode, proc.stdout, proc.stderr))

    print(f"ran={len(specs)} failed={len(failures)}")
    for cmd, rc, stdout, stderr in failures[:10]:
        print("CMD:", " ".join(cmd))
        print("RC:", rc)
        print("STDOUT:", stdout)
        print("STDERR:", stderr)

    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
