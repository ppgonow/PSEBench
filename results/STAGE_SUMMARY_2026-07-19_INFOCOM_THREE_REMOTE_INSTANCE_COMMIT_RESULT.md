# Three-remote-instance commit-bound replication result (2026-07-19)

## Outcome

The complete amended protocol passed in one fresh reportable attempt. The
authorization, gateway, and effect roles ran on three authorized remote Docker
instances and communicated through loopback-only, SSH-tunneled HTTP. The public
topology audit verifies three distinct boot, DMI product UUID, cgroup/container,
hostname, PID/network/UTS namespace, CPU-info, and resolved SSH endpoint hashes.
It also records the shared cloned machine-ID hash and shared SSH proxy hash.

| Policy | Invalid effects committed | Benign TCR |
|---|---:|---:|
| Check-once | 100/100 | 50/50 |
| PAuth-style/pre-action | 100/100 | 50/50 |
| PCAS-style/pre-action | 100/100 | 50/50 |
| Receipt-bound | 0/100 | 50/50 |

Each stale-versus-receipt-bound same-ID exact McNemar test gives
`p=1.5777218104420236e-30`. Receipt-bound ASR is 0/100 with a Wilson 95% upper
bound of 0.036995; stale-policy ASR is 100/100 with a lower bound of 0.963005.
Every one of the 400 attack-policy rows passed the logical active-mutation gate
immediately before the gateway request.

Every fifth scenario scheduled duplicate downstream delivery. Across the full
matrix, 600 delivery attempts produced 500 unique ledger commits. The 100
allowed duplicate rows made two attempts and one ledger row; the 20 scheduled
receipt-bound attack duplicates were blocked with no delivery or ledger row.

Benign median/p95 gateway latency was 301.796/470.254 ms for check-once,
181.276/471.815 ms for PAuth-style, 283.882/483.257 ms for PCAS-style, and
466.798/647.823 ms for receipt-bound. These values include multiple SSH relay
legs and exhibit transport/scheduling variability; they are remote-path
observations, not a receipt-verification microbenchmark or production latency
claim.

## Independent acceptance checks

- Complete matrix: 600 rows, 600 unique policy/scenario keys, 150 IDs per
  policy.
- Causal gate: 400/400 attack rows active immediately before commit request.
- Outcomes: 300 stale invalid commits, 0 receipt-bound invalid commits, and
  200/200 benign task completions.
- Idempotence: 120 scheduled duplicate rows, 100 delivered duplicates, 600
  attempts, and 500 unique ledger rows.
- Topology: three service identities and three hashes for every amended
  independence signal; one shared machine-ID hash and one shared proxy hash.
- Health: 3/3 loopback service checks and 3/3 gateway relay evidence fields.
- Daemon-free audit: regenerated summary, paired, and integrity CSVs are
  byte-identical to the released files.
- Local regression: 87/87 unit tests passed after the run.
- Cleanup: all three instances independently reported zero experiment
  directories and zero experiment service processes.

## Claim boundary

This replication strengthens evidence that the check-to-commit result survives
separation across three live remote container instances and SSH-relayed service
boundaries. It reuses the same 150 scenarios and is not pooled with process or
same-host Docker results as independent samples. The identity evidence does not
prove three physical machines, independent administration, independent failure
domains, direct private-network transport, production traffic, TLS properties,
or distributed-transaction semantics. PAuth-style and PCAS-style remain typed
adaptations, not official system reproductions.

## Public output hashes

| File | SHA-256 |
|---|---|
| `analysis/multihost_commit_race_detail.csv` | `dc803838d75a50b2d6f66cea5e7f715e1d40a5277e8490e1e17e1a152f152794` |
| `analysis/multihost_commit_race_summary.csv` | `36ce79a243d23f1fe296a468521ea4f8cddbb547cd08dfd0e1985a5f6fa7500b` |
| `analysis/multihost_commit_race_paired.csv` | `67057393e6ae0a83a088bd3e995118d8754a6348ebee9e6348a00769a307e4ef` |
| `analysis/multihost_commit_race_topology.csv` | `08f69cfdfffe65c6a75774beccc93fde7a2d06414617ff52a1e4bb60a7665b15` |
| `analysis/multihost_commit_race_audit_integrity.csv` | `e12f5b22a6b57ae1bd34afc71e511774d6d5d285a0e1aa13d120f3378acf49f0` |

The remote raw JSONL, raw identifiers, SSH configuration, HMAC, logs, and
SQLite ledger remain local. The protocol amendment and implementation freeze
were recorded before the reportable matrix was run.
