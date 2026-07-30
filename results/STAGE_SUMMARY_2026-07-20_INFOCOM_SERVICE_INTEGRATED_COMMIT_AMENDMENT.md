# INFOCOM service-integrated condition-isolation amendment (2026-07-20)

## Invalid first formal invocation

The first formal 540-row invocation is discarded in full. It reached final
validation and failed on `critical-window/service-atomic` confirmation controls.
The runner wrote no public detail, summary, or integrity CSV because publication
occurs only after all frozen gates pass. The child process, temporary database,
WAL files, and in-memory HMAC key were removed after failure.

The failure was cross-condition state contamination. The first invocation used
one SQLite database for all four schedule/policy cells. A confirmation nonce
consumed correctly in the earlier `pre-transaction/service-atomic` cell
remained in the global nonce table when the same frozen scenario was repeated
as a distinct observation in `critical-window/service-atomic`. The later
control was therefore blocked even though its own trial state was stable.

No failed row, timing, event sequence, database entry, or partial aggregate is
reportable or reusable.

## Frozen correction

Each schedule/policy cell will run in a fresh service-integrated effect process
with a fresh temporary SQLite database. Scenario state, effect rows, nonce
consumptions, and linearization sequences therefore cannot cross condition
boundaries. The same run-level in-memory HMAC key may be shared across cells;
it is never persisted or released.

This correction changes only condition isolation and service lifecycle. It does
not change the 150-scenario corpus, 120-scenario critical-window subset,
policies, schedules, 10-ms hold, duplicate-delivery rule, commit protocol,
metrics, causal gates, or frozen aggregate totals. After the correction and
regression tests, the formal matrix must restart from the first cell and may
publish only after all 540 rows pass.
