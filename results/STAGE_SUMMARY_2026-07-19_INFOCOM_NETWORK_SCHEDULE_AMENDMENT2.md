# INFOCOM cross-service schedule transport amendment 2 (2026-07-19)

## Invalid formal attempt

The first formal command was discarded in full. It wrote no public detail or
summary CSV and left no service process. The non-reportable SQLite diagnostic
shows that the first three profiles completed before both requests in the first
concurrent profile timed out. No completed row, ledger entry, or timing from
this attempt will be reused.

The failure follows accumulated transient HTTP/1.1 connection churn rather
than a policy or schedule invariant: the single-request, delayed, and
downstream-duplicate profiles completed, then concurrent new client connections
stalled. This is the same transport class previously isolated by the load
benchmark.

## Frozen transport correction

This experiment will opt into the already tested standard-library
`PersistentJsonPool` path:

- the schedule client pre-establishes bounded authorization, gateway, and
  effect connections before measurement;
- `ServiceCluster(pooled_http=True)` gives the gateway bounded persistent
  authorization/effect connections;
- pool size four covers the mutation request plus two concurrent status/commit
  attempts without changing application-level concurrency;
- the original 600-row matrix retains its non-pooled default.

Connection establishment remains outside reported per-profile latency. The
scenarios, policies, profiles, logical request delays and order, service delays,
mutation hold, payloads, decisions, expected counts, causal gates, and summary
metrics are unchanged.

The code and tests must be re-frozen, then the non-reportable pilot reruns from
an empty temporary database. A successful formal run must restart at the first
profile with `--overwrite`; no prior row is retained.
