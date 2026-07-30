# INFOCOM native-proposal three-service commit bridge result (2026-07-21)

## Formal execution

The pre-registered matrix completed once with no infrastructure or gate
failure. It replayed the 192 frozen authorized clean native proposals (48 per
requested alias) through three distinct loopback HTTP processes:
authorization, gateway, and effect. No model endpoint was contacted.

Each proposal was cloned unchanged across cached-pre-action/receipt-bound and
stable/revoked conditions, producing 768 rows and 768 unique keys. For every
revoked row, the authorization service first propagated version 7 to 8 into
the authoritative effect state. The client observed the 1,000 ms mutation as
applied and not completed, waited 10 ms, checked the active gate again, and
only then sent the commit through the gateway.

## Results

| Requested alias | Cached stable | Receipt stable | Cached revoked stale commit | Receipt revoked stale commit | Exact McNemar $p$ |
|---|---:|---:|---:|---:|---:|
| GPT-5.5 | 48/48 | 48/48 | 48/48 | 0/48 | $7.11\times10^{-15}$ |
| Grok-4.5 | 48/48 | 48/48 | 48/48 | 0/48 | $7.11\times10^{-15}$ |
| GPT-5.4 | 48/48 | 48/48 | 48/48 | 0/48 | $7.11\times10^{-15}$ |
| GPT-5.6-sol | 48/48 | 48/48 | 48/48 | 0/48 | $7.11\times10^{-15}$ |

Across aliases, both policies committed 192/192 stable controls.
Cached-pre-action committed 192/192 stale revoked effects, whereas
receipt-bound committed 0/192. These are per-proposal policy clones, not 768
independent model samples. Aliases remain separate strata and are not pooled
for inference.

## Causal and integrity gates

- 384/384 revoked rows observed mutation applied before commit.
- 384/384 revoked rows observed mutation still active immediately before the
  gateway request.
- 384/384 revoked rows recorded commit after the client-side observation.
- 768/768 rows preserved the canonical native effect hash through
  authorization, receipt, gateway receipt/forwarding, effect request, and
  authoritative state.
- Every allowed row produced exactly one effect-ledger row; every blocked row
  produced zero, yielding 576 effect rows from 768 delivery attempts.
- 768/768 rows passed the authorization/gateway/effect role-chain gate.
- Startup verified three distinct child processes, loopback-only listeners,
  role health, and authorization/effect plus gateway/effect relays.
- Public topology contains only salted SHA-256 identity commitments and
  non-identifying capability fields.
- The ephemeral HMAC, SQLite database, service processes, and listeners were
  destroyed after the run.

An independent, credential-free audit reconstructed the raw/detail key set,
per-alias cells, exact paired tests, causal gates, hash and ledger invariants,
integrity totals, and anonymized topology. All 65 checks passed. Repository
unit tests pass 131/131.

## Interpretation boundary

This replication removes the remaining stitching concern: the same frozen
native effect that receives authorization is the effect relayed to and decided
at a real downstream service boundary. It establishes the causal consequence
of a controlled post-check revocation, conditional on an authorized native
proposal. It does not estimate how often revocation occurs in deployed agents,
does not create new model observations, and does not establish WAN or
production-scale behavior.

## Artifacts

- `runner/run_native_service_commit_bridge.py`
- `analysis/audit_native_service_commit_bridge.py`
- `results/native_service_commit_bridge/native_service_commit_bridge.jsonl`
- `results/native_service_commit_bridge/native_service_commit_bridge_attempts.jsonl`
- `analysis/native_service_commit_bridge_detail.csv`
- `analysis/native_service_commit_bridge_summary.csv`
- `analysis/native_service_commit_bridge_paired.csv`
- `analysis/native_service_commit_bridge_integrity.csv`
- `analysis/native_service_commit_bridge_topology.csv`
- `analysis/native_service_commit_bridge_audit.csv`

