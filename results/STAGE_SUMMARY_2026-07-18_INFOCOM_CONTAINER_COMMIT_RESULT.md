# Container-isolated commit-bound replication result (2026-07-18)

## Outcome

The complete amended protocol passed. Three Docker containers provided
separate authorization, gateway, and SQLite effect-ledger network namespaces
on one same-host user-defined bridge. The public topology audit verifies three
distinct container-ID hashes, namespace hashes, and IP addresses; every
published test port is bound to `127.0.0.1`. Read-only roots, dropped
capabilities, no-new-privileges, and non-root users were active for all roles.

| Policy | Invalid effects committed | Benign TCR |
|---|---:|---:|
| Check-once | 100/100 | 50/50 |
| PAuth-style/pre-action | 100/100 | 50/50 |
| PCAS-style/pre-action | 100/100 | 50/50 |
| Receipt-bound | 0/100 | 50/50 |

Each stale-versus-receipt-bound same-ID exact McNemar test gives
`p=1.5777218104420236e-30`. Each of the five invalidation families separately
has 20/20 versus 0/20 discordance (`p=1.9073486328125e-06`). All 400 attack
policy observations confirm active mutation immediately before the gateway
request.

Every fifth scenario schedules duplicate downstream delivery. Across the
complete matrix, 600 delivery attempts produce 500 unique ledger commits:
allowed duplicates have two attempts and one ledger row, while blocked rows
have no attempt and no ledger row.

On the 50 benign controls, check-once gateway median/p95 latency is
5.730/12.316 ms and receipt-bound latency is 9.464/12.229 ms. The median
increase is 3.734 ms and includes the additional authorization-state HTTP
fetch. Host and container scheduling noise makes this a system-path latency
observation, not a microbenchmark.

## Claim boundary

This independently audited replication strengthens evidence that the
check-to-commit result survives process and network-namespace separation. It
does not add independent scenarios and is not pooled with the three-process
experiment. It remains one Docker Desktop host with a monitor-controlled key
and one local bridge; under the recorded network amendment the bridge is not
marked Docker `internal`. It is not multi-host, cloud-provider,
independently-administered production-service, egress-isolation, or distributed
transaction evidence. PAuth-style and PCAS-style are typed adaptations, not
official system reproductions.

## Public outputs

| File | SHA-256 |
|---|---|
| `analysis/container_commit_race_detail.csv` | `40bd405f6b015c22e178bbab7a8e363497ed167fe0ff71d13db6478149ed587f` |
| `analysis/container_commit_race_summary.csv` | `cb3f340819fa3dd9dcb18325b2aed33a8faa21789ca0406dac7c6d584bace217` |
| `analysis/container_commit_race_paired.csv` | `67057393e6ae0a83a088bd3e995118d8754a6348ebee9e6348a00769a307e4ef` |
| `analysis/container_commit_race_topology.csv` | `222129c4def1ad2d42d572141589957c1d5ccba922bf80db9f9183ed81c10ae9` |
| `analysis/container_commit_race_audit_integrity.csv` | `f523650b5316ff83c1bc89cd25c3cffb170766aa022563a098311e8a42bbc158` |

The ephemeral HMAC key, raw Docker identifiers, raw JSONL, and SQLite file stay
local. The network and Bash compatibility amendments were recorded before the
successful complete matrix.
