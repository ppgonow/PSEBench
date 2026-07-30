# INFOCOM receipt-field ablation plan (2026-07-21)

## Status and purpose

This document freezes the experiment before implementation or execution. The
experiment tests whether each field checked by the receipt-bound verifier is
necessary for its corresponding check-to-commit invalidation. It also adds an
online commit-time reauthorization baseline so the paper does not attribute a
security advantage to the receipt when a stronger current-state check ties it.

This is a new experiment. Existing commit-race results and paper versions are
not overwritten or pooled with it.

## Frozen corpus and matrix

- Corpus: the existing 150 files in `scenarios/commit-race-heldout/`.
- Families: effect substitution, authorization revocation, principal switch,
  confirmation replay, and lease expiry.
- Per family: 20 attacks and 10 stable controls.
- Policies, frozen in this order:
  - `receipt-full`
  - `receipt-no-principal`
  - `receipt-no-authorization-version`
  - `receipt-no-exact-effect`
  - `receipt-no-expiry`
  - `receipt-no-confirmation-nonce`
  - `online-reauthorize-at-commit`
- Total: 7 policies x 150 scenarios = 1,050 unique observations.

Every receipt policy authenticates the complete receipt. An ablation disables
only the named comparison with current commit state. The nonce ablation
disables both nonce equality and one-use consumption checks. It does not
disable receipt authentication. Online reauthorization consumes the trusted
grant, current authoritative context, and commit effect directly and does not
consume a receipt.

## Pre-specified hypotheses

- `receipt-full` and `online-reauthorize-at-commit` block all 100 invalidated
  commits and complete all 50 controls.
- Each single-field ablation commits the 20 attacks in its matching family,
  blocks the other 80 attacks, and completes all 50 controls.
- No policy/scenario row may be deleted, replaced, or selectively repeated.

Any deviation is retained and treated as either a failed hypothesis or an
implementation defect. The code may be corrected only after a dated amendment,
and a corrected run must use a fresh output prefix.

## Outputs and metrics

- Detail CSV and JSONL with scenario ID, family, policy, decision, reason,
  committed flag, ASR/TCR labels, and code/corpus hashes.
- Family-by-policy summary with Wilson 95% confidence intervals.
- Same-ID exact McNemar comparisons against `receipt-full`.
- Integrity table requiring 1,050 rows, 1,050 unique keys, 700 attacks, 350
  controls, and exact per-cell denominators.
- A field-by-family heatmap may be derived only from the frozen detail file.

## Boundary

The run is local and credential-free. It uses an ephemeral HMAC key held only
in process memory and commits only to a temporary SQLite ledger. It does not
contact external services. This experiment establishes field necessity in the
frozen state-transition model; it is not a cryptographic-strength evaluation
or a prevalence study.
