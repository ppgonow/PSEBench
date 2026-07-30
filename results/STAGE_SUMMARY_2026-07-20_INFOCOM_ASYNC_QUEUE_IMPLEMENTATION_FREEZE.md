# INFOCOM asynchronous queue implementation freeze (2026-07-20)

## Status

The loopback-only durable broker, formal runner, daemon-free auditor, and
guardrail tests are frozen before the first formal 600-row invocation. The
second 40-row pilot covers all five invalidation families, both policies, both
profiles, broker restart, payload substitution, acknowledgement loss, release,
redelivery, and effect-ledger idempotence.

Pilot outcome:

- 40 rows and 40 unique keys;
- check-once/receipt-bound stale commits: 10/0;
- controls completed: 20/20;
- duplicate rows and queue/effect attempts: 40 and 80;
- restart rows/gates: 20/20;
- allowed duplicate rows with idempotent second effect attempt: 30/30;
- queued or inflight messages after each cell: zero.

Pilot data remain under `tmp/` and are not reportable evidence.

## Frozen hashes

| File | SHA-256 |
|---|---|
| `runner/durable_async_queue.py` | `6fa2ba00c97a4f854862fa7ef9288d81057dcf6ee0840e0f7baabf07d334f30b` |
| `runner/run_async_queue_commit.py` | `86f102801efe2e6d78d046a666638f62eadd192ddbf2baaa16f943724cd136a5` |
| `analysis/audit_async_queue_commit.py` | `adbf87c78fd2e5ca3ea3ac62862516acd06f5148045160213680c326884e9a7b` |
| `tests/test_durable_async_queue.py` | `758095f24c99373db2002e8518dd967035d61febfec2671f2e6c4627923eef56` |
| `scenarios/commit-race-heldout/MANIFEST.csv` | `2fcdadacae83242b61754567ba00c61c79a5e4738c676009fac0985f0203b028` |
| `scenarios/commit-race-heldout/BINDING_SNAPSHOT_SHA256.txt` | `55a86cb3ccdfbb3c01ca2848df2b49875938b7cae9176154d1199ad3cbf8d291` |
| pilot detail | `9ae233f3b24ec94de97aa7368939160f73f282a9cc10aa9b96395f61609a7955` |
| pilot summary | `83ba3249a843a990a937fa824cec7a4311892e17304a63f31ae7d8585a88f0f3` |
| pilot integrity | `18c360c88272ad34d92370d5fea4bb80fc8d97fe25e86b714706954575d7fa2d` |

Eight focused broker and service-transaction unit tests pass. No experiment
broker/effect process or temporary directory remains after the pilot.

## Formal-run rule

The formal invocation must use the default non-overwrite output prefix and the
complete frozen scenario directory. Any failure invalidates that invocation;
no partial CSV may be retained or combined with another attempt. Any code,
scenario, policy, protocol, or gate change requires a dated amendment before a
fresh invocation.
