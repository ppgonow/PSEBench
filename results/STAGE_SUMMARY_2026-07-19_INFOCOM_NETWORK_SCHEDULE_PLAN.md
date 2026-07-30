# INFOCOM cross-service transport-schedule plan (2026-07-19)

## Research question

Does receipt-bound authorization remain correct when cross-service commit
requests are delayed, duplicated, retried concurrently, or delivered in an
order different from the client's logical attempt order?

This experiment is a controlled three-process loopback HTTP schedule stress. It
does not estimate WAN fault prevalence, independently administered-domain
behavior, or production capacity.

## Frozen inputs

- scenarios: all 150 frozen entries in `scenarios/commit-race-heldout/`;
- policies: `check-once` and `receipt-bound`;
- authorization/effect service delay: 0.5 ms;
- attack mutation hold: 100 ms;
- actual services: authorization, gateway, and SQLite-backed effect roles in
  three distinct OS processes communicating through HTTP;
- authentication: a fresh in-memory 256-bit HMAC key for each run.

## Frozen schedules

| Profile | Gateway attempts | Client dispatch | Effect delivery |
| --- | ---: | --- | --- |
| `single` | 1 | 2 ms after the mutation-active gate | one delivery |
| `delayed-40ms` | 1 | 40 ms after the mutation-active gate | one delivery |
| `duplicate-downstream` | 1 | 2 ms after the gate | two identical deliveries |
| `concurrent-retry` | 2 | both logical attempts after 2 ms | one delivery per allow response |
| `reordered-retry` | 2 | attempt 1 after 20 ms; attempt 2 immediately | attempt 2 must arrive first |

For controls, the same dispatch profiles run without mutation. Duplicate and
retry profiles use one trial ID, so the effect ledger must retain one commit
even when it observes two deliveries.

## Frozen matrix and gates

- 5 profiles x 2 policies x 150 scenarios = 1,500 unique result rows;
- 1,000 attack rows must show every gateway request arriving after mutation
  application and before mutation completion;
- all 300 `reordered-retry` rows must show logical attempt 2 arriving before
  logical attempt 1;
- all 500 invalidation rows under `check-once` must commit and all 500 under
  `receipt-bound` must block;
- all 500 control rows must complete;
- allow rows must have exactly one ledger row; blocked rows must have zero;
- frozen totals are 2,100 gateway attempts, 1,600 effect deliveries, and 1,000
  unique ledger commits;
- summary reports per-profile/policy ASR, TCR, gateway attempts, effect
  deliveries, ledger rows, and client p50/p95/p99 latency;
- latency is descriptive because profiles intentionally impose different
  schedules.

## Execution discipline

The runner writes public detail and summary CSVs only after the complete matrix
passes all gates. A non-reportable pilot uses one attack and one control per
profile/policy and writes no public CSV. Any pilot-driven code or protocol
change requires a dated amendment before the formal run. A failed formal run is
discarded in full rather than resumed or combined with another attempt.

## Expected public outputs

- `analysis/network_schedule_detail.csv`
- `analysis/network_schedule_summary.csv`
- daemon-free independent reconstruction from
  `analysis/audit_network_schedule.py`
