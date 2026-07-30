#!/usr/bin/env bash
set -euo pipefail

image="docker.io/library/postgres@sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193"
image_reference="postgres:17-alpine"
image_digest="sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193"
container="psebench-postgres-portability-$PPID-$RANDOM"
password="$(openssl rand -hex 24)"
python=".venv/bin/python"

if [[ ! -x "$python" ]]; then
  python="python3"
fi
if ! "$python" -c 'import psycopg' >/dev/null 2>&1; then
  echo "psycopg is required; install requirements.txt" >&2
  exit 1
fi

cleanup() {
  unset PSEBENCH_POSTGRES_DSN password
  docker stop "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker run --detach --rm \
  --name "$container" \
  --publish 127.0.0.1::5432 \
  --env POSTGRES_USER=psebench \
  --env POSTGRES_PASSWORD="$password" \
  --env POSTGRES_DB=psebench \
  "$image" >/dev/null

ready=0
for _ in {1..60}; do
  if docker exec "$container" pg_isready --quiet --username psebench --dbname psebench; then
    ready=1
    break
  fi
  sleep 0.25
done
if [[ "$ready" -ne 1 ]]; then
  echo "PostgreSQL container did not become ready" >&2
  exit 1
fi

port="$(docker port "$container" 5432/tcp | sed -n 's/.*://p' | head -n 1)"
if [[ ! "$port" =~ ^[0-9]+$ ]]; then
  echo "failed to resolve loopback PostgreSQL port" >&2
  exit 1
fi
export PSEBENCH_POSTGRES_DSN="postgresql://psebench:${password}@127.0.0.1:${port}/psebench"

host_ready=0
for _ in {1..60}; do
  if "$python" -c \
    'import os, psycopg; c = psycopg.connect(os.environ["PSEBENCH_POSTGRES_DSN"], connect_timeout=2); c.execute("SELECT 1").fetchone(); c.close()' \
    >/dev/null 2>&1; then
    host_ready=1
    break
  fi
  sleep 0.25
done
if [[ "$host_ready" -ne 1 ]]; then
  echo "PostgreSQL loopback connection did not become ready" >&2
  exit 1
fi

"$python" runner/run_postgres_integrated_commit.py \
  --image-reference "$image_reference" \
  --image-digest "$image_digest" \
  "$@"
