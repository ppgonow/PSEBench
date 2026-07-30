#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$root/runner/run_multihost_commit_race.py" "$@"

if [[ " $* " != *" --preflight-only "* ]]; then
  python3 "$root/analysis/audit_multihost_commit_race.py" \
    --output-prefix "$root/analysis/multihost_commit_race_audit"
fi
