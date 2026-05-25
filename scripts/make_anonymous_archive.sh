#!/usr/bin/env bash
set -euo pipefail

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Refusing to archive: commit or stash local changes first." >&2
  exit 1
fi

mkdir -p dist
out="dist/PSEBench-anonymous-artifact.zip"
git archive --format=zip --output="$out" HEAD
echo "$out"
