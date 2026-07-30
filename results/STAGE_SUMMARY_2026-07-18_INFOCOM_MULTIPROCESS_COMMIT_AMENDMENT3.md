# Multiprocess commit experiment causal-timing amendment (2026-07-18)

## Third invalid attempt and diagnostic

The third fresh-database attempt was rejected before JSONL or CSV output even
after the commit client waited for mutation-applied status. A single-scenario
diagnostic then showed that cross-process comparisons of `perf_counter_ns()`
were false despite the client-observed causal ordering. Process-local monotonic
timestamps are suitable for durations within one process, not as a portable
cross-process ordering oracle.

## Frozen audit correction

The next complete run replaces cross-process timestamp comparison with a causal
HTTP observation. After the authorization service reports mutation applied,
the commit client waits the frozen 2 ms, queries the authorization service again,
and requires both conditions before sending the gateway request:

- `mutation_applied_ns` is present; and
- `mutation_completed_ns` is absent.

This establishes over HTTP that invalidation is active immediately before the
gateway request without comparing clocks from different processes. The
receipt-bound gateway still queries current authorization state and blocks on
the state lock until mutation completes; stale pre-action policies do not.

No policy outcome, scenario, denominator, delay, retry schedule, or ledger rule
changes. The fourth attempt must restart from a fresh database. The paper and
result report must disclose all three rejected infrastructure attempts and must
describe the timing evidence as causal status observation, not synchronized
cross-process timestamps.

Post-correction hashes before the fourth attempt:

- Runner: `09c01d2bb822061db970291b65403558bbcee542540cc57eddda3848e226dfcb`
- Tests: `2703c174640a803d2f9e10350311a2e0e0cc3ca7862e2f2ebb65bbeb86432d23`
