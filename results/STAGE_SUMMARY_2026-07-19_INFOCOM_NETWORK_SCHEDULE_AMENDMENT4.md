# INFOCOM cross-service schedule SQLite-serialization amendment 4 (2026-07-19)

## Invalid third formal attempt

The third formal command is discarded in full. It wrote no public detail or
summary CSV and left no service process. The `single`, `delayed-40ms`, and
`duplicate-downstream` profiles completed internally. During
`concurrent-retry/receipt-bound`, after all 100 attack trials and ten benign
trials, both gateway attempts lost their effect-service connection and the
effect child exited with `SIGSEGV`. No row, timing, or SQLite entry from this
invocation is reportable or reusable.

An OS crash diagnostic localized the fault to SQLite statement execution in
the effect process. The raw diagnostic is not part of the artifact because it
contains host-identifying metadata. Code inspection identified the matching
concurrency defect: `/commit` serialized SQLite access, but two concurrently
blocked receipt-bound attempts both use `/count`, whose queries shared the same
`check_same_thread=False` connection without acquiring the ledger lock.

## Frozen implementation correction

All access to the effect service's single SQLite connection, including
read-only count queries, will acquire one re-entrant ledger lock. Re-entrancy
is required because `/commit` performs its final count while already holding
that lock. A regression test will issue concurrent count requests against the
same effect service and check the final idempotent ledger totals.

This is an implementation-safety correction at the temporary ledger. It does
not change the receipt protocol, scenario corpus, policies, profile schedules,
delays, mutation/reorder gates, payloads, decision expectations, metrics, or
frozen aggregate totals. After code and tests are frozen again, both the pilot
and formal matrix must restart from the first profile with `--overwrite`.
