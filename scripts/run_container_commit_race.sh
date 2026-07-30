#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="$root/container/commit-race/compose.yaml"
run_dir="$root/tmp/container_commit_race_runtime-$$"
effect_dir="$run_dir/effect"
key_file="$run_dir/commit_hmac"
project="psebench-commit-race-$$"

if [[ -e "$root/analysis/container_commit_race_detail.csv" ]]; then
  echo "Container experiment output already exists; a frozen amendment is required before retry." >&2
  exit 1
fi

mkdir -p "$effect_dir"
chmod 0777 "$effect_dir"
umask 077
python3 -c 'import pathlib,secrets,sys; pathlib.Path(sys.argv[1]).write_text(secrets.token_hex(32), encoding="ascii")' "$key_file"

export PSEBENCH_EFFECT_DIR="$effect_dir"
export PSEBENCH_HMAC_FILE="$key_file"

choose_port() {
  python3 - <<'PY'
import socket

sock = socket.socket()
sock.bind(("127.0.0.1", 0))
print(sock.getsockname()[1])
sock.close()
PY
}

export PSEBENCH_AUTH_PORT="$(choose_port)"
export PSEBENCH_GATEWAY_PORT="$(choose_port)"
export PSEBENCH_EFFECT_PORT="$(choose_port)"

cleanup() {
  docker compose --project-name "$project" --file "$compose_file" down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -f "$key_file"
}
trap cleanup EXIT

docker compose --project-name "$project" --file "$compose_file" build
docker compose --project-name "$project" --file "$compose_file" up --detach

authorization_url=""
gateway_url=""
effect_url=""
authorization_container=""
gateway_container=""
effect_container=""
for role in authorization gateway effect; do
  container_id="$(docker compose --project-name "$project" --file "$compose_file" ps --quiet "$role")"
  if [[ -z "$container_id" ]]; then
    echo "Missing container for $role" >&2
    exit 1
  fi
  case "$role" in
    authorization) authorization_container="$container_id" ;;
    gateway) gateway_container="$container_id" ;;
    effect) effect_container="$container_id" ;;
  esac
done

for role in authorization gateway effect; do
  deadline=$((SECONDS + 60))
  while true; do
    binding="$(docker compose --project-name "$project" --file "$compose_file" port "$role" 8080 2>/dev/null || true)"
    if [[ "$binding" == 127.0.0.1:* ]]; then
      url="http://$binding"
      if python3 - "$url" <<'PY'
import json
import sys
from urllib.request import Request, urlopen

request = Request(
    sys.argv[1] + "/health",
    data=b"{}",
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urlopen(request, timeout=2) as response:
    payload = json.loads(response.read())
if payload.get("role") not in {"authorization", "gateway", "effect"}:
    raise SystemExit(1)
PY
      then
        case "$role" in
          authorization) authorization_url="$url" ;;
          gateway) gateway_url="$url" ;;
          effect) effect_url="$url" ;;
        esac
        break
      fi
    fi
    if (( SECONDS >= deadline )); then
      echo "Timed out waiting for $role health endpoint" >&2
      docker compose --project-name "$project" --file "$compose_file" ps >&2
      exit 1
    fi
    sleep 0.25
  done
done

python3 "$root/runner/run_container_commit_race.py" \
  --authorization-url "$authorization_url" \
  --gateway-url "$gateway_url" \
  --effect-url "$effect_url" \
  --authorization-container "$authorization_container" \
  --gateway-container "$gateway_container" \
  --effect-container "$effect_container"

python3 "$root/analysis/audit_container_commit_race.py" \
  --output-prefix "$root/analysis/container_commit_race_audit"
