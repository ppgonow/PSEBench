# INFOCOM Local HTTP/SQLite Commit-Race Result (2026-07-16)

## Execution

The experiment followed
`results/STAGE_SUMMARY_2026-07-16_INFOCOM_HTTP_COMMIT_RACE_PLAN.md` without
changing its corpus, policies, timing, endpoints, outcomes, or exclusion rules.
It executed all 150 frozen scenarios under both `check-once` and
`commit-bound`, for 300 unique policy/scenario observations. No credential,
model, or external network service was used.

Check, mutation, and commit crossed separate requests to a threaded localhost
HTTP service. Attack mutation and commit clients were released together; the
commit request was delayed by 1 ms while the mutation handler remained active
for 3 ms after applying state. Allowed commits were inserted by the server into
a fresh SQLite sandbox ledger.

## Integrity checks

- 300/300 expected policy/scenario keys were present.
- Both policies used the same 150 scenario IDs.
- 200/200 attack-policy observations recorded mutation before serialized
  commit.
- 200/200 attack-policy observations recorded overlapping mutation and commit
  HTTP request intervals.
- Every allowed decision had exactly one ledger row and every blocked decision
  had zero rows.
- The final ledger contained 200 rows: 100 invalid and 50 valid under
  `check-once`, plus 50 valid under `commit-bound`.

## Results

| Policy | Attack commits | ASR (Wilson 95% CI) | Valid controls | TCR (Wilson 95% CI) |
| --- | ---: | ---: | ---: | ---: |
| `check-once` | 100/100 | 1.000 [0.963, 1.000] | 50/50 | 1.000 [0.929, 1.000] |
| `commit-bound` | 0/100 | 0.000 [0.000, 0.037] | 50/50 | 1.000 [0.929, 1.000] |

Every transition family independently repeats 20/20 versus 0/20 ASR and 10/10
TCR. The overall exact paired McNemar result is
`p=1.5777218104420236e-30`; each 20-pair family result is
`p=1.9073486328125e-06`.

The actual SQLite state, rather than a self-reported decision, supplies the
commit outcome. Under stale `check-once`, all 100 invalid post-check states are
written. Authenticated commit binding blocks all 100 while retaining every
stable control.

## Evidence boundary

This materially strengthens the earlier deterministic transition replay by
adding wall-clock overlapping requests, HTTP serialization, and an observable
database side effect. It remains an orchestrated localhost experiment in one
process with monitor-controlled authentication and atomic state. It is not a
language-model experiment, native agent tool-calling evidence, concurrent
external-service evidence, or a distributed transaction test.

Public derived outputs are `analysis/http_commit_race_detail.csv`,
`analysis/http_commit_race_summary.csv`, and
`analysis/http_commit_race_paired.csv`. Raw request records and the SQLite file
are generated locally under `results/http_commit_race/` and remain gitignored.

