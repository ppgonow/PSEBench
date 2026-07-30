# INFOCOM PostgreSQL service-atomic portability result (2026-07-20)

## Outcome

The amended fresh PostgreSQL run completed and passed the frozen 540-row
matrix. This is the sole reportable PostgreSQL portability result. The earlier
causal-observation failure and pre-scenario infrastructure failure remain
excluded in full and are retained in their dated reports.

| Schedule | Policy | Attack stale commits | Controls complete | Deliveries | Effects | Nonces |
|---|---|---:|---:|---:|---:|---:|
| pre-transaction | gateway-split | 100/100 | 50/50 | 180 | 150 | 0 |
| pre-transaction | service-atomic | 0/100 | 50/50 | 180 | 50 | 10 |
| critical-window | gateway-split | 80/80 | 40/40 | 144 | 120 | 0 |
| critical-window | service-atomic | 0/80 | 40/40 | 144 | 120 | 30 |

Integrity totals are 540 rows, 540 unique keys, 360 attack rows, 180 controls,
108 duplicate rows, 648 delivery attempts, 440 effect rows, and 40 nonce rows.
All 80 critical-window service-atomic attacks pass the verifier gate, request
mutation after verification, expose the blocked PostgreSQL row-lock interval,
and linearize effect commit before mutation.

## Backend and transaction boundary

- PostgreSQL server: 17.10
- isolation: `READ COMMITTED`
- driver: Psycopg 3.3.4
- image digest:
  `sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193`
- lock: `SELECT ... FOR UPDATE` on the per-trial authorization-state row

Current-state receipt verification, exact-effect comparison, optional nonce
consumption, trial-ID deduplication, linearization event insertion, and effect
insertion share one PostgreSQL transaction. This is service-local atomicity,
not a transaction across independently managed databases.

## SQLite comparison

The PostgreSQL and SQLite detail files contain the same 540
schedule/policy/scenario keys. For every key, the following discrete fields
match exactly: attack, task, committed effect, authorization at linearization,
duplicate schedule, delivery attempts, effect rows, nonce rows, idempotent
second delivery, and effect-before-mutation serialization. Backends are reported
as separate replications and are not pooled as `n=1080`.

Client latency is not compared because the PostgreSQL amendment uses a 30 ms
critical-window observation hold while the SQLite matrix uses 10 ms. The
portability claim concerns transaction outcomes and causal order only.

## Independent audit and cleanup

`analysis/audit_postgres_integrated_commit.py` reconstructs the summary and
integrity files from the released detail CSV without PostgreSQL, Docker, a DSN,
or a credential. It passes all frozen totals and metadata gates.

The launch script stopped and removed the disposable container. A post-run
check found no experiment container. The password, DSN, random loopback port,
HMAC key, database contents, and runtime logs are absent from public outputs.

## Public file hashes

| File | SHA-256 |
|---|---|
| `analysis/postgres_integrated_commit_detail.csv` | `fa3864bd3896ed214264bb97e636a8b975e03d6c51f5ed73c5df43856d106fb8` |
| `analysis/postgres_integrated_commit_summary.csv` | `feb5cb13182ddc76d54917c87a978a4a7e52fdbd71b0a6a7c4c7290304440404` |
| `analysis/postgres_integrated_commit_integrity.csv` | `b1b25af2fd7d0b28466cecab4b758be443521e5d914579b3c01bfa67afdd3183` |
| `analysis/postgres_integrated_commit_metadata.csv` | `cd01fd3471ef127c061fa768f77ed8ade6df5bc7c9a3eeb3aed4f519af0f9893` |
