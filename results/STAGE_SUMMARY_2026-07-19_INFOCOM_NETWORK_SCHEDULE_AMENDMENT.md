# INFOCOM cross-service schedule causal-gate amendment (2026-07-19)

## Invalid pilot

The first non-reportable pilot completed service execution but failed its first
attack-row causal gate. It wrote no public detail or summary CSV. The temporary
SQLite file and all pilot timings are non-reportable and will be overwritten.

The runner compared `perf_counter_ns` values emitted by the authorization and
gateway processes. Although the request completed during the 100 ms mutation
hold, treating independent process timestamp origins as a causal ordering gate
is not portable and yielded a false inactive result.

## Frozen correction

The correction replaces cross-process timestamp comparison with logical
happens-before evidence:

1. each logical gateway attempt sleeps for its frozen profile delay;
2. that same worker queries authorization `/mutation-status`;
3. it requires `mutation_applied` and not `mutation_completed` in the returned
   state;
4. it immediately sends the gateway `/commit` request;
5. the row passes only if every attack attempt passes this pre-send gate.

The reordered profile still compares the two request-received timestamps
inside the single gateway process, where they share one clock. No timestamp is
compared across roles or machines.

The scenarios, policies, five schedules, delays, 100 ms hold, service delays,
matrix size, expected outcomes, delivery/ledger totals, latency metrics, and
all other gates remain unchanged. The pilot restarts from an empty temporary
database and again writes no public CSV. Updated code and test hashes must be
recorded before rerunning it.
