# INFOCOM service-integrated atomic commit result (2026-07-20)

## Status

The amended formal invocation completed the frozen 540-row matrix and wrote
public CSVs only after every outcome, causal, transaction-order, duplicate, and
cleanup gate passed. The independent daemon-free audit reconstructed the
summary and integrity tables byte-for-byte from the released detail CSV.

The first formal invocation is not part of this result. It failed because one
database was incorrectly reused across repeated schedule conditions, allowing
an earlier condition's confirmation-nonce consumption to contaminate a later
control. It published no CSV. The dated amendment records that failure and the
pre-rerun correction to a fresh process and database per schedule/policy cell.

## Frozen outcomes

| Schedule | Policy | Rows | Invalidations | Stale commits | Controls | Tasks |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| pre-transaction | gateway-split | 150 | 100 | 100 | 50 | 50 |
| pre-transaction | service-atomic | 150 | 100 | 0 | 50 | 50 |
| critical-window | gateway-split | 120 | 80 | 80 | 40 | 40 |
| critical-window | service-atomic | 120 | 80 | 0 | 40 | 40 |

For all 80 `critical-window/service-atomic` attacks, the mutation request was
issued only after receipt verification completed while the effect transaction
remained open. All 80 mutation requests were observed before they acquired the
SQLite write lock, and all 80 database event sequences place effect commit
before mutation application. The corresponding authorized effects commit; no
stale effect commits. In the split comparator, mutation applies between the
external verifier and effect write in all 80 cases, producing 80 stale commits.

Across the complete matrix:

- rows and unique schedule/policy/scenario keys: 540/540;
- attack rows: 360; control rows and completed controls: 180/180;
- split/atomic stale commits: 180/0;
- duplicate rows: 108;
- delivery attempts: 648;
- effect rows: 440;
- same-ID duplicate allowed deliveries: one effect row each;
- transaction-bound confirmation-nonce consumptions: 40;
- distinct child effect-service role gate: 540/540.

These results establish service-local atomic coupling of current-state receipt
verification, nonce consumption, trial-ID idempotence, and SQLite effect commit.
They do not establish cross-database distributed atomicity, consensus,
active-channel integrity, WAN prevalence, or production scale.

## Public files

| File | SHA-256 |
| --- | --- |
| `analysis/service_integrated_commit_detail.csv` | `7708fba37d0fe981f2b035a20a59facebe3a77d464ef75e533002aaa2e9a3feb` |
| `analysis/service_integrated_commit_summary.csv` | `94b41f9e4d72f9d84a282a8d818f0e60d816ec1acc0af65686806bbbc659c0fd` |
| `analysis/service_integrated_commit_integrity.csv` | `33ee0488fff1ea765814a89fb8e5577b6e32d4ea9351b8010621f8fa6978b5e8` |
| `runner/service_integrated_commit.py` | `20c160f6e255013d9019d410e75be9e3f245394f0e6cd93ca7f26a288dc713ba` |
| `runner/run_service_integrated_commit.py` | `1869493245ba29ef15c808b715a6d9d24d330c43411aa0b7b718850abc8bdbd3` |
| `analysis/audit_service_integrated_commit.py` | `7cb6c0ca716ac67b3649bfea0194325604d6e556efe2e30882fb6de3b69494d5` |
| `tests/test_service_integrated_commit.py` | `59a1de0b207b92fafe7c45c7eb433bcf5739891053c7b8196044a3bcd911d7fa` |

The four temporary SQLite databases and WAL files were removed after
validation. The child processes terminated normally. The public files contain
no HMAC key, database, process ID, port, runtime timestamp, host identifier, or
network address.
