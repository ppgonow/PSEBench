# INFOCOM PostgreSQL service-atomic portability plan (2026-07-20)

## Question and claim boundary

This follow-up asks whether the service-integrated receipt invariant reproduces
under a second transactional implementation rather than depending on SQLite's
database-wide writer serialization. It is a backend-portability replication,
not a new independent attack sample, a production-capacity benchmark, or a
claim that database transactions are novel.

## Frozen implementation condition

- Backend: PostgreSQL 17 Alpine image
  `docker.io/library/postgres@sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193`.
- Driver: Psycopg 3.x with binary libpq packaging.
- Isolation: PostgreSQL `READ COMMITTED`.
- Concurrency boundary: mutation and atomic commit acquire a row lock on the
  same `authorization_state` record with `SELECT ... FOR UPDATE`.
- Atomic path: current-state receipt verification, exact-effect comparison,
  optional one-use nonce consumption, trial-ID deduplication, linearization
  event insertion, and effect insertion occur in one database transaction.
- Split path: the gateway verifies before invalidation and the effect service
  accepts the later write without receipt revalidation, matching the existing
  gateway-split comparator.
- Condition isolation: each schedule/policy condition uses a new PostgreSQL
  schema. No nonce, trial ID, or effect state is shared across conditions.
- Exposure: the disposable PostgreSQL container binds only a random
  `127.0.0.1` host port and uses a fresh random password. It has no persistent
  volume and is stopped after success or failure.

## Frozen matrix

The matrix reuses the already frozen `scenarios/commit-race-heldout/` corpus
without modifying scenario text, timing, policy logic, or labels:

- pre-transaction: 100 invalidations plus 50 controls per policy;
- critical-window: 80 context invalidations plus 40 controls per policy;
- policies: `gateway-split` and `service-atomic`;
- atomic post-verification hold: 10 ms;
- every fifth scenario receives one byte-identical duplicate delivery.

This yields exactly 540 unique backend/schedule/policy/scenario rows. The
PostgreSQL rows remain a separate replication and are not pooled with the
SQLite rows for confidence intervals or sample-size claims.

## Frozen success gates

- 540 rows and 540 unique schedule/policy/scenario keys;
- gateway-split stale commits: 100/100 pre-transaction and 80/80 critical;
- service-atomic stale commits: 0/100 pre-transaction and 0/80 critical;
- all 180 benign controls complete;
- all 80 critical atomic mutations are requested after verification, remain
  blocked at the row-lock gate, and linearize after the effect commit;
- 108 duplicate rows produce 648 delivery attempts;
- every allowed trial has exactly one effect row and every blocked trial has
  zero effect rows;
- expected one-use nonce and idempotency totals match the SQLite matrix;
- an independent no-service audit reconstructs all totals from released CSV.

Any infrastructure error, missing row, unexpected retry, failed causal gate,
or code/configuration change invalidates the whole run. Failed attempts remain
documented and are never selectively merged with a later run. A formal matrix
may begin only after unit/integration checks and an implementation-freeze
record are complete.

## Planned public outputs

- `analysis/postgres_integrated_commit_detail.csv`
- `analysis/postgres_integrated_commit_summary.csv`
- `analysis/postgres_integrated_commit_integrity.csv`
- `analysis/postgres_integrated_commit_metadata.csv`
- `analysis/audit_postgres_integrated_commit.py`
- a dated result report containing only non-identifying backend metadata and
  aggregate outcomes.

The DSN, password, container ID, local port, runtime logs, HMAC key, and raw
database remain local and are excluded from the anonymous artifact.
