# INFOCOM PostgreSQL portability infrastructure failure (2026-07-20)

## Disposition

The first retry is invalid and excluded. It failed before scenario registration
and produced no experimental observation.

## Failure

The container-local `pg_isready` probe passed, but the first Psycopg connection
through Docker's randomly assigned `127.0.0.1` host port was closed while the
runner queried backend metadata. The host-side port-forwarding path was not yet
ready even though PostgreSQL was ready inside the container.

No `analysis/postgres_integrated_commit_*.csv` file was created. No trial,
receipt, mutation, effect, nonce, or ledger row ran. The disposable container,
password, database, and loopback port were removed.

This is an infrastructure-readiness failure, not a protocol result. A retry
requires a dated readiness amendment and a fresh container.
