# INFOCOM service-integrated atomic commit plan (2026-07-20)

## Motivation and evidence boundary

The existing receipt-bound reference path verifies in a trusted gateway and
then calls a separate SQLite effect service. It establishes gateway decisions
and idempotent delivery, but it does not establish atomic coupling between
receipt verification and effect commit. This new experiment closes that
implementation gap without replacing or pooling the earlier matrices.

The experiment runs only against the frozen synthetic corpus on loopback. It
does not estimate race prevalence, WAN behavior, active-channel integrity,
distributed consensus, or production capacity.

## Frozen implementation

The effect service owns the authoritative commit state and a temporary SQLite
ledger. Each `service-atomic` attempt executes the following steps under one
`BEGIN IMMEDIATE` transaction:

1. check the trial-ID idempotency ledger;
2. read the current principal, authorization version, exact effect, lease, and
   confirmation-nonce state;
3. authenticate and verify the receipt against the supplied effect and current
   state;
4. consume a non-null confirmation nonce;
5. insert the committed effect and audit attempt; and
6. commit the transaction.

Mutation requests use a separate SQLite connection and the same authoritative
state table. Therefore, a mutation that requests the write lock after receipt
verification cannot apply before the effect transaction commits. The
`gateway-split` comparator verifies outside the effect transaction and then
uses an unverified effect-write endpoint, matching the gap in the earlier
trusted-gateway reference deployment.

The service binds only to `127.0.0.1`, runs in a distinct child process, uses a
fresh in-memory 256-bit HMAC key, and deletes the temporary database after the
complete run. The key, database, process ID, and runtime timestamps are not
released.

## Frozen scenarios and schedules

- corpus: the existing 100 invalidations and 50 controls under
  `scenarios/commit-race-heldout/`;
- policies: `gateway-split` and `service-atomic`;
- `pre-transaction`: all 150 scenarios; attack mutations must apply after
  check-time receipt issuance and before the effect request;
- `critical-window`: the 120 authorization-revocation, principal-switch,
  confirmation-replay, and lease-expiry scenarios; for attacks, mutation is
  requested only after the verifier gate;
- fixed atomic post-verification hold: 10 ms;
- duplicate delivery: every fifth scenario ID, using the same trial ID.

Effect substitution is intentionally absent from `critical-window`: a final
payload different from the receipt is rejected at verification and is not a
post-verification context mutation. It remains present in all 150
`pre-transaction` rows.

The frozen matrix is 300 `pre-transaction` rows plus 240 `critical-window`
rows, for 540 unique schedule/policy/scenario observations. Repeated scenarios
across schedules are not independent statistical units and will not be pooled
as such.

## Frozen causal and outcome gates

- 540 rows and 540 unique keys;
- 360 attack rows and 180 control rows;
- `pre-transaction`: all 200 attack rows observe mutation applied before the
  effect request;
- `critical-window/gateway-split`: all 80 attack rows observe an allow at the
  external verifier, then mutation applied before effect commit;
- `critical-window/service-atomic`: all 80 attack rows observe verifier entry,
  mutation request before effect commit, no mutation lock acquisition or
  application before effect commit, and mutation application after commit;
- `gateway-split`: 100/100 and 80/80 invalid commits in the two schedules;
- `service-atomic`: 0/100 and 0/80 invalid commits;
- all 180 controls complete;
- every allowed trial has exactly one effect row; every blocked trial has zero;
- 108 duplicate rows produce two delivery attempts but at most one effect row;
- total delivery attempts: 648; total effect rows: 440;
- stable non-null confirmation nonces are consumed in the same transaction;
  same-trial duplicate delivery returns the existing result without a second
  effect.

Any implementation, corpus, schedule, hold, or metric change after this plan
requires a dated amendment before a new formal run. A failed formal run is
retained as failed and cannot be selectively resumed or combined.

## Expected public outputs

- `analysis/service_integrated_commit_detail.csv`;
- `analysis/service_integrated_commit_summary.csv`;
- `analysis/service_integrated_commit_integrity.csv`;
- an independent daemon-free reconstruction in
  `analysis/audit_service_integrated_commit.py`;
- a dated result report with hashes and cleanup status.
