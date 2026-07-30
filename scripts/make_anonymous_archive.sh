#!/usr/bin/env bash
set -euo pipefail

mode="head"
if [[ "${1:-}" == "--worktree" ]]; then
  mode="worktree"
elif [[ -n "${1:-}" ]]; then
  echo "Usage: $0 [--worktree]" >&2
  exit 2
fi

mkdir -p dist
out="dist/PSEBench-anonymous-artifact.zip"

if [[ "$mode" == "head" ]]; then
  if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
    echo "Refusing to archive HEAD: commit or stash local changes, or use --worktree for a review snapshot." >&2
    exit 1
  fi
  git archive --format=zip --output="$out" HEAD
else
  file_list="$(mktemp)"
  trap 'rm -f "$file_list"' EXIT
  git ls-files -z --cached --others --exclude-standard > "$file_list"
  python3 - "$out" "$file_list" <<'PY'
from pathlib import Path
import sys
import zipfile

output = Path(sys.argv[1])
file_list = Path(sys.argv[2]).read_bytes().split(b"\0")
root = Path.cwd().resolve()

with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for raw_path in file_list:
        if not raw_path:
            continue
        relative = Path(raw_path.decode("utf-8"))
        lower = relative.as_posix().lower()
        basename = relative.name.lower()
        if (
            basename.startswith("screenlog")
            or basename.startswith(".env")
            or relative.suffix.lower() in {".log", ".sqlite", ".sqlite3", ".db", ".key", ".pem", ".token"}
        ):
            raise SystemExit(f"Refusing to archive local log, database, or credential file: {relative}")
        source = root / relative
        if source.is_symlink():
            raise SystemExit(f"Refusing to archive symlink: {relative}")
        if source.is_file():
            archive.write(source, relative.as_posix())
PY
fi

echo "$out"
