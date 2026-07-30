# Multiprocess commit-bound comparison plan (2026-07-18)

## Status and registration boundary

This protocol is specified locally before outcome execution. The scenario
manifest, implementation, tests, policy names, denominators, timing checks, and
exclusion rules are frozen before the complete matrix is run. There is no
external timestamped registry, so the paper must call this experiment
pre-specified or frozen-before-execution rather than externally pre-registered.

## Question

Does authorization that succeeds at proposal time remain valid when the effect
or authorization context changes before a separate service commits the effect?
The comparison isolates commit binding from request interpretation by giving all
four policies the same authorized and checked typed effect.

## Execution surface

Three distinct OS processes communicate only over HTTP loopback:

1. An authorization-state service issues the initial allow and stores mutable
   principal, authorization version, effect, expiry, and confirmation state.
2. A commit gateway either trusts the cached allow or queries current state and
   verifies the authenticated receipt.
3. An effect service owns an independent SQLite ledger and idempotently commits
   allowed effects.

This is a multi-process network service decomposition on one host. It is not a
multi-host deployment, independently administered production service, or
distributed transaction.

## Frozen matrix

- Corpus: the existing 150-scenario commit-race manifest.
- Composition: 100 invalidations and 50 matched stable controls.
- Families: effect substitution, authorization revocation, principal switch,
  confirmation replay, and lease expiry.
- Policies: `check-once`, `PAuth-style/pre-action`,
  `PCAS-style/pre-action`, and `receipt-bound`.
- Total: 600 policy/scenario observations.
- Typed literature-inspired rows are adaptations, not official implementations.
- Every fifth scenario deterministically receives a duplicate downstream
  delivery attempt; the effect service must retain exactly one ledger row.

## Frozen checks and outcomes

- ASR: an invalid-at-commit effect reaches the effect-service ledger.
- Benign-control TCR: a stable authorized effect reaches the ledger.
- Every attack request must record mutation-before-decision and overlapping
  mutation/commit request intervals.
- All three service PIDs must be distinct child processes.
- Allowed rows must have exactly one ledger commit; blocked rows must have none.
- Duplicate delivery rows must have two attempts and one ledger commit.
- Comparisons use same-ID exact McNemar tests and Wilson intervals.
- Benign-control gateway median/p95 latency is reported per policy.

The run is reportable only if all 600 keys and every integrity check pass. No
failed observation may be dropped, replaced, or counted as a new sample.

## Pre-execution hashes

| Artifact | SHA-256 |
|---|---|
| Runner | `b3edb577df9f389106ee18316ba6a1845c0dd6ad367358d92952443afc766418` |
| Tests | `1876bae72ce929d69245f0c7592f9166a1d3bc31f5f04e63e23dab9644f9300e` |
| Scenario manifest | `2fcdadacae83242b61754567ba00c61c79a5e4738c676009fac0985f0203b028` |
| Commit-binding module | `c605a40ce0512ab7d518573ff91da95a0822f6276e4a6ae5803e6074830f9cd5` |
