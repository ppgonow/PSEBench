# Multiprocess commit-bound comparison result (2026-07-18)

## Claim boundary

This experiment decomposes authorization state, commit enforcement, and effect
storage into three distinct OS processes connected only through HTTP loopback.
It compares stale proposal-time authorization with receipt-bound commit on the
same 150 frozen state-transition scenarios. PAuth-style and PCAS-style rows are
typed pre-action adaptations, not official implementations. PCAS-style is an
internal policy-compilation authorization label motivated by FORGE, not a named
reproduced system.

The result is single-host multi-process network-service evidence. It is not a
multi-host deployment, independently administered production-service test,
human confirmation study, or distributed transaction.

## Completed matrix

- 150 scenarios: 100 invalidations and 50 matched stable controls.
- Four policies and 600 unique policy/scenario observations.
- Three service roles used three distinct child-process PIDs.
- All 400 attack observations confirmed through HTTP that mutation was applied
  and not completed immediately before the gateway request.
- Every allowed effect has exactly one SQLite ledger row; every blocked effect
  has none.
- Same-ID exact McNemar comparisons have no missing or reverse pairs.

## Security and utility

| Policy | Attack commits | Benign tasks | Exact paired p vs receipt-bound |
|---|---:|---:|---:|
| Check-once | 100/100 | 50/50 | `1.58e-30` |
| PAuth-style/pre-action | 100/100 | 50/50 | `1.58e-30` |
| PCAS-style/pre-action | 100/100 | 50/50 | `1.58e-30` |
| Receipt-bound | 0/100 | 50/50 | -- |

Each of the five invalidation families independently yields 20/20 stale-policy
attack commits and 0/20 receipt-bound commits. The overall Wilson 95% intervals
are [0.963, 1.000] for 100/100 and [0, 0.037] for 0/100.

This does not show that IACG makes a better proposal-time authorization decision
than PAuth- or PCAS-style monitors. It shows that an otherwise correct
proposal-time decision is stale unless it is cryptographically bound to the
exact effect and current state revalidated at the downstream commit boundary.

## Network-path latency and retry behavior

Benign-control gateway latency includes HTTP dispatch and the isolated effect
service's fixed 0.5 ms delay. Receipt-bound additionally performs an HTTP state
fetch and commit verification.

| Policy | Median gateway latency | p95 gateway latency |
|---|---:|---:|
| Check-once | 2.399 ms | 4.659 ms |
| PAuth-style/pre-action | 2.249 ms | 4.429 ms |
| PCAS-style/pre-action | 2.328 ms | 4.492 ms |
| Receipt-bound | 4.078 ms | 7.014 ms |

Relative to check-once, receipt-bound adds 1.679 ms to the median benign
gateway path in this single-host decomposition. Of 120 deterministically
scheduled duplicate-delivery rows, 100 reached the effect service because 20
receipt-bound attacks were blocked first. The effect service recorded 600
delivery attempts but only 500 unique commits, preserving one ledger row per
allowed trial.

## Invalid infrastructure attempts

Three complete-matrix attempts were rejected before reportable JSONL/CSV output:

1. An 8 ms mutation hold did not guarantee request overlap.
2. Increasing the hold to 30 ms did not fix unsynchronized request arrival.
3. Waiting for mutation-applied status exposed that process-local monotonic
   timestamps were not a portable cross-process ordering oracle.

The final run uses causal HTTP status observation: mutation must be applied and
not completed immediately before the gateway request. The two protocol
amendments and all rejected-attempt boundaries are retained alongside the
original plan.

## Reproduction and hashes

```bash
python3 analysis/audit_multiprocess_commit_race.py \
  --detail analysis/multiprocess_commit_race_detail.csv \
  --output-prefix tmp/multiprocess_commit_race_audit
```

| Artifact | SHA-256 |
|---|---|
| Detail CSV | `c3e9af242f7f40cc46286cc3b3187adbcff39a4bf9d0a115f57d9de47274acce` |
| Summary CSV | `31e42cd52e5a2170e343a9151617f2c381aee557baa6813d25660a5def737443` |
| Paired CSV | `67057393e6ae0a83a088bd3e995118d8754a6348ebee9e6348a00769a307e4ef` |
| Local raw JSONL | `1cf4d264ca4020913b4153027ee17074db0d44bd984811c8b2c79cd1b099711d` |

The raw JSONL and SQLite database are local-only. The timestamp-free detail,
summary, paired, and integrity CSVs are sufficient for public count and pairing
reproduction.
