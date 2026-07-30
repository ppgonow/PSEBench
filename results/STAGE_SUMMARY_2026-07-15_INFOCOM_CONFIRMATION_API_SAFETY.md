# INFOCOM Confirmation Matrix: API Safety Gate (2026-07-15)

## Scope

This stage hardens the pending model-driven confirmation experiment. It does
not report model results. No credential was configured and no API request was
made during this safety audit. The runner remains decision-only: it asks for a
structured approval decision and never invokes a tool or commits an external
effect.

## Frozen Matrix and Hard Limits

- 20 balanced scenarios: 10 benign and 10 attacks.
- Two framings: `neutral` and `contaminated`.
- Three models, giving exactly 120 logical jobs.
- One sequential worker, with a minimum 1-second inter-job interval; the
  documented experiment uses 2 seconds.
- A default hard ceiling of 150 actual HTTP attempts, including retries.
- At most two retries for HTTP 429/502/503/504 and connection/timeout failures,
  using capped exponential or `Retry-After` delays.

The live path also requires HTTPS unless an explicit trusted-local HTTP
override is supplied. It rejects duplicate models or framings, unsafe run IDs,
matrices larger than the logical budget, a request ceiling below the logical
matrix size, and an existing nonempty output without `--resume`.

## Resume, Accounting, and Redaction

Each result row records the actual HTTP attempts consumed by that logical job,
including a job whose final retry fails. Failed and parse-error rows remain in
the raw JSONL for auditability but are not considered complete by `--resume`.
The request ceiling is global to the experiment and stops execution immediately
when exhausted. On resume, prior attempts are reconstructed from the raw JSONL,
so restarting the process cannot reset the 150-attempt ceiling.
Stored error strings redact the configured key, bearer tokens, and strings
matching the common `sk-` credential prefix.

The summarizer keeps the last row for each
`(model, framing, scenario_id)` key. A reportable summary must declare the
expected models and contain the exact model/framing Cartesian product, exactly
20 unique rows per cell, and the same scenario IDs in every cell. Partial
summaries require the explicit diagnostic-only `--allow-incomplete` flag. A
reportable summary also rejects any unresolved API or parse error and records
the actual HTTP-attempt total across retries and resume rows.

## No-Network Verification

The following paths were exercised with both `OPENAI_API_KEY` and
`OPENAI_BASE_URL` removed from the environment:

- the normal dry run printed 20 scenarios, two framings, three models, 120
  logical calls, and the 120/150 hard budgets, then exited successfully;
- duplicate models were rejected;
- a zero-second live interval was rejected;
- four models (160 logical calls) were rejected by the 120-call ceiling;
- an existing nonempty output was rejected before credential lookup;
- a live invocation without a credential was rejected before entering the
  request loop.

The focused confirmation suite contains 16 passing tests covering the balanced
matrix, decision parsing, bounded retry, request-budget exhaustion, terminal
retry accounting, cumulative resume budgeting, error redaction, resume
semantics, deduplication, complete six-cell validation, unresolved-error
rejection, cross-cell scenario-ID consistency, same-ID framing pairs, exact
McNemar/Holm calculations, and exact-power thresholds. The final
repository-wide sanity entry point discovers 64 tests; 63 execute and pass in
the managed sandbox, while one localhost HTTP test is skipped when socket
binding is prohibited. It also validates all 908 scenario schemas and all 61
reconstructed INFOCOM claims.

## Execution Gate

The 120-call matrix should be run only after the previously disclosed key has
been revoked and a newly rotated key is supplied through an environment
variable. Do not place a credential in the repository, a command argument, a
shell history entry, or a result file. Completion of this safety gate does not
authorize use of the previously exposed credential.
