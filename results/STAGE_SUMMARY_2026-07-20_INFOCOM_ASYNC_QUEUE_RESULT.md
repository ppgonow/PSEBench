# INFOCOM asynchronous queue commit result (2026-07-20)

## Outcome

The first formal invocation completed the frozen 600-row matrix and wrote the
public CSVs only after all completeness, causality, FIFO, broker-restart,
redelivery, idempotence, identity, and cleanup gates passed. A daemon-free
auditor reconstructed the summary and integrity outputs byte-for-byte from the
detail CSV.

| Profile | Policy | Stale commits | Controls complete | Duplicate rows | Deliveries | Effects |
|---|---|---:|---:|---:|---:|---:|
| steady consumer | check-once | 100/100 | 50/50 | 30 | 180 | 150 |
| steady consumer | receipt-bound | 0/100 | 50/50 | 30 | 180 | 50 |
| broker restart | check-once | 100/100 | 50/50 | 30 | 180 | 150 |
| broker restart | receipt-bound | 0/100 | 50/50 | 30 | 180 | 50 |

The complete matrix contains 600 rows and 600 unique
profile/policy/scenario keys, 400 attack rows, 200 controls, 120 scheduled
ack-loss/redelivery rows, 720 broker deliveries, 720 effect-service attempts,
400 effect rows, and 20 nonce consumptions. All 400 attacks satisfy the logical
`enqueue acknowledged -> mutation acknowledged -> first delivery` gate. All
300 broker-restart rows are delivered by a new broker process from the same
temporary queue database, and all 600 first deliveries preserve FIFO order.

Every message is acknowledged exactly once, and every cell finishes with zero
queued or inflight messages. Every allowed duplicate has two effect-service
attempts but one effect row; blocked receipt-bound duplicates remain blocked on
both attempts. The 80 effect-substitution attack rows replace an unclaimed
queued payload exactly once while retaining the original receipt.

## Interpretation

The matrix closes the synchronous-only schedule gap. An enqueue-time allow is
not sufficient when authorization changes before an asynchronous consumer
reaches the effect boundary: check-once commits all stale effects in both
profiles. Receipt-bound transaction verification blocks every stale delivery,
including after broker restart, while preserving stable controls and
at-least-once idempotence.

The broker is a loopback-only, SQLite-backed reference with explicit
enqueue/claim/release/ack semantics. These results do not establish compatibility
with a production broker, partitions, multi-tenant isolation, WAN prevalence,
cross-database atomicity, or independent administration. The two profiles reuse
the same 150 scenarios and are reported separately rather than pooled.

## Reproduction and cleanup

`analysis/audit_async_queue_commit.py` validates the frozen 600-key matrix and
reconstructs the summary and integrity CSVs without a broker, effect service,
HMAC key, port, process identifier, or database. The formal runner refused
pre-existing output and wrote files only after the complete matrix passed.

The broker and effect processes terminated normally. All temporary broker/effect
SQLite files, WAL files, HMAC material, ports, process identifiers, and runtime
logs were removed or excluded from public output. A post-run check found no
experiment process or temporary run directory.

## Public file hashes

| File | SHA-256 |
|---|---|
| `analysis/async_queue_commit_detail.csv` | `657cedd6360f9303a548b6594d59e8484aa62653bb3ed58fa7bcbf6b71033559` |
| `analysis/async_queue_commit_summary.csv` | `f2c3353ddff0a50f3e6478a217247d767cf941b945949162014056da6e303113` |
| `analysis/async_queue_commit_integrity.csv` | `36910c57470d79ff37cb050246f37c20fff40779a189ea36dbf36ce5e7664581` |
| `runner/durable_async_queue.py` | `6fa2ba00c97a4f854862fa7ef9288d81057dcf6ee0840e0f7baabf07d334f30b` |
| `runner/run_async_queue_commit.py` | `86f102801efe2e6d78d046a666638f62eadd192ddbf2baaa16f943724cd136a5` |
| `analysis/audit_async_queue_commit.py` | `adbf87c78fd2e5ca3ea3ac62862516acd06f5148045160213680c326884e9a7b` |
| `tests/test_durable_async_queue.py` | `758095f24c99373db2002e8518dd967035d61febfec2671f2e6c4627923eef56` |
