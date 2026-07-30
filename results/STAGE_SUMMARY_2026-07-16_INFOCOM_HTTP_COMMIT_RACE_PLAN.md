# INFOCOM Local HTTP Commit-Race Analysis Plan (2026-07-16)

## Status and question

This plan is frozen before running the local HTTP experiment. It asks whether
an authorization decision made before a mutable state transition remains safe
when check, mutation, and commit cross separate HTTP request boundaries and the
observable commit is written to a SQLite sandbox ledger.

This experiment does not involve a language model, an external provider, or a
distributed deployment. It upgrades the existing deterministic state-machine
replay to wall-clock, multi-request execution on localhost; it must not be
reported as model-driven or distributed-system evidence.

## Frozen design

- Corpus: all 150 scenarios in `scenarios/commit-race-heldout/`, generated and
  frozen before this runner: 100 invalid transitions and 50 matched valid
  controls across authorization revocation, principal switch, effect
  substitution, confirmation replay, and lease expiry.
- Policies: paired `check-once` and `commit-bound` runs for every scenario,
  producing exactly 300 policy/scenario observations.
- Check boundary: an HTTP request validates the checked effect. The
  `commit-bound` policy additionally receives an authenticated HMAC receipt
  over principal, authorization version, effect, time window, and optional
  confirmation nonce.
- Transition boundary: attack scenarios send the frozen post-check effect and
  commit context in a separate HTTP mutation request. The client starts the
  mutation and commit workers together, delays commit by 1 ms, and keeps the
  mutation handler active for 3 ms after applying the transition. This creates
  an orchestrated overlapping-request window while ensuring the frozen
  transition is visible before commit. Controls omit the mutation request.
- Commit boundary: a separate HTTP request applies either the cached
  `check-once` allow decision or verifies the receipt against current state.
  An allowed commit is inserted into a SQLite ledger by the server. Outcomes
  are derived from the server decision and ledger row, not agent text.
- Runtime: one fresh local threaded HTTP server, an ephemeral HMAC key held
  only in process memory, and a fresh SQLite database. No external network or
  credential is used.

## Outcomes and hypotheses

The primary attack outcome is an invalid-at-commit effect present in the
SQLite ledger. The primary utility outcome is a valid control effect present
in the ledger. The manipulation check requires every attack row to record a
mutation timestamp before the serialized commit and overlapping HTTP request
intervals.

Primary hypotheses, fixed before execution:

1. `check-once` permits invalid commits after the frozen state transition.
2. `commit-bound` rejects those invalid commits.
3. Both policies preserve valid matched controls.

Report ASR and TCR with Wilson 95% intervals overall and by transition family.
Use exact paired McNemar tests for the attack comparison overall and by family.
Report request-overlap and mutation-before-commit counts as manipulation
checks. Do not treat repeated policy observations as independent scenarios.

## Failure and exclusion rules

The run is reportable only if all 300 unique policy/scenario keys are present,
both policies contain the same 150 scenario IDs, every HTTP response is valid,
every allowed commit has exactly one matching ledger row, every blocked commit
has none, and all 200 attack policy rows pass both timing manipulation checks.
No failed row may be silently dropped or retried as a new statistical unit.
Any infrastructure failure invalidates the run until the complete matrix is
rerun from a fresh database.

