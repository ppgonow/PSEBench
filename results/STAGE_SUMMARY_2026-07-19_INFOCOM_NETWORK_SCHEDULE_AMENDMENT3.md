# INFOCOM cross-service schedule service-lifecycle amendment 3 (2026-07-19)

## Invalid second formal attempt

The second formal command is discarded in full. It wrote no public CSV and
left no service process. It completed the first three profiles and ten benign
rows of `concurrent-retry/receipt-bound`, after which one child service received
`SIGKILL` and both in-flight gateway connections closed. The system reported no
global memory pressure. No completed row, ledger entry, or timing is reused.

A non-reportable isolated diagnostic then executed all 50 benign
`concurrent-retry/receipt-bound` scenarios successfully with the same pools,
delays, service code, and payloads. This isolates the failure to accumulated
service lifetime/state after roughly 900 preceding trials, not to the profile's
concurrency or policy behavior.

## Frozen lifecycle correction

Each schedule profile will run in a fresh three-process `ServiceCluster` with a
fresh temporary SQLite file. All five clusters are still created and completed
sequentially inside one runner invocation. The runner retains all rows only in
memory, validates the complete 1,500-row union, and writes public CSVs only
after every profile succeeds. A failure in any profile invalidates the entire
invocation.

The same in-memory HMAC key is used across the five profile clusters. Trial IDs
are already profile-qualified, and no protocol state or comparison crosses
profiles, so restarting roles does not change an observational unit. Reported
latency still excludes process, connection, and pool startup.

The scenarios, policies, profile schedules, causal/reorder gates, service and
mutation delays, payloads, expected decisions, 2,100 gateway attempts, 1,600
effect deliveries, 1,000 ledger commits, and all summary metrics remain
unchanged. The pilot and formal run both restart from their first profile with
`--overwrite` after updated code/tests are frozen.
