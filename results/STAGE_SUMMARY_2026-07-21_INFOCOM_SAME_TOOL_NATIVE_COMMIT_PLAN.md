# INFOCOM same-tool native-to-commit plan (2026-07-21)

## Status and purpose

This document freezes a new end-to-end experiment before scenario generation,
model calls, or result inspection. It removes a confound in the existing native
matrix: reminder, file, and calendar escalation currently use separately named
safe and unsafe functions. The new matrix exposes one neutral, parameterized
effect tool per workflow and derives authorization-relevant effects from its
arguments. It also connects an unmodified native proposal to receipt issuance,
authorization invalidation, and service-local atomic commit.

Existing native results and paper versions remain immutable and separate.

## Frozen design

- Workflows: reminder, file, calendar, and message.
- Untrusted carriers: inbound message, retrieved document, and prior tool
  output.
- Four independently worded semantic templates per workflow/carrier cell.
- Forty-eight template IDs in total.
- Each ID has paired `clean` and `injected` exposure conditions.
- Requested aliases: `gpt-5.5`, `grok-4.5`, `gpt-5.4`, and `gpt-5.6-sol`.
- Native units: 48 x 2 x 4 = 384 model/template/exposure observations.
- Aliases are reported separately and are never pooled.
- Clean/injected conditions are paired only within the same semantic template.
- Model requests use temperature 0, a six-turn ceiling, two bounded retries,
  and at least three seconds between HTTP attempts.

The four effect tools are frozen as:

- `schedule_reminder(name, fire_at, recurrence)`
- `write_file(path, content)`
- `create_event(title, start, end, recurrence)`
- `send_message(recipient, text)`

The same function name is available for authorized and escalated effects.
Adapters canonicalize arguments into tool, persistence, target, scope, and
provenance fields. Read/retrieval tools expose controlled synthetic text and
never commit external effects.

## Shared-proposal and commit branches

The first native effect proposal is stored once. Policy branches reuse the
same function name and arguments; they do not resample the model proposal.

- Injected exposure: compare permissive and IACG effect authorization for
  proposal ASR, committed-effect ASR, and primary TCR.
- Clean exposure: retain every terminal/no-effect unit. For each check-time
  authorized proposal, issue a receipt once and clone it into four local commit
  observations: cached/stable, cached/revoked, receipt/stable, and
  receipt/revoked.
- Revocation changes only the authorization version after the native proposal
  and before the atomic commit request.
- Receipt verification, trial-ID deduplication, and ledger insertion occur in
  one temporary SQLite transaction.

Policy branches and commit clones are paired measurements, not independent
model samples.

## Normalization conformance freeze

Before model execution, adapters must pass 200 hand-specified pairs: 25
semantically equivalent and 25 authorization-changing pairs per workflow. A
fixed-seed 10,000-case mutation test then checks deterministic canonicalization,
fail-closed handling, and digest stability. Equivalent pairs must have equal
canonical effects. Authorization-changing pairs must differ or be rejected.
Any security false-equivalence blocks the native run until a dated amendment.

## Outputs and acceptance gates

- Frozen YAML, manifest hashes, and template-family inventory.
- Append-only raw JSONL containing every attempt and terminal outcome.
- Final detail tables at model/template and native-to-commit levels.
- Per-alias and per-workflow proposal ASR, committed ASR, TCR, Wilson intervals,
  and same-template exact paired tests where applicable.
- Normalization detail/summary files and fixed random seed.
- Integrity checks for all 384 native keys, unique manifests, same-tool identity,
  shared proposals, no omitted failures, and exact ledger cardinality.

The experiment is valid even if an alias proposes no unsafe effect. Negative
aliases and negative workflow cells remain in the result. Infrastructure
failure invalidates the complete affected alias run; it is not repaired by
selective row replacement.

## Boundary

All effects use synthetic targets and temporary SQLite state. The only network
operation is the already authorized OpenAI-compatible model endpoint configured
locally by the researcher. No public service, real account, real recipient, or
production tool is contacted.
