# Independent final review: expanded local persistence v2

Status: PASS. Review completed after the frozen main run; no experimental
artifacts or frozen sources were changed by the reviewer.

The independent reviewer used its own response parser and occurrence-set
observer, without importing the runner or released auditor. The review checks
implementation and artifact consistency; it is not a replication administered
by another institution or an independent production provider.

## Coverage and consistency

- Frozen protocol, runner, auditor and calibration bindings match. Calibration
  independently replays all 16 responses as valid, complete and authorized.
- Main raw data contain exactly 768 assigned keys in frozen order, with each
  model attempted 192 times. No replacement, retry, API error or budget skip.
- All 1,536 ledger branches and observed rows match independent response/state
  replay; all 1,259 committed schedules match their candidate fields and exact
  occurrence sets. Unknown records remain unknown.
- All 32 summary cells and 16 framing-pair cells match independent computation,
  including missing pairs, assigned denominators and missingness bounds.
- Summary CSV: 32 rows; by-grant CSV: 256 rows, each assigned denominator 6.
  All fields match independent aggregation, with no omitted or duplicate rows.
- Main valid/interface counts: Qwen173/19, Mistral158/34, Gemma192/0,
  Llama181/11. Total704 valid and64 interface failures; 43,258 output tokens.
- No model lifecycle errors. Main elapsed time3,285.50 seconds.

## Outcome interpretation checks

Contaminated unmediated unauthorized-registration counts, permissive then
prompt-only, each out of48 assigned instances:

| Model | Unauthorized | Unknown | Complete task |
|---|---:|---:|---:|
| Qwen2.5 | 5 / 5 | 6 / 6 | 34 / 8 |
| Mistral | 4 / 5 | 11 / 9 | 33 / 34 |
| Gemma | 2 / 0 | 0 / 0 | 30 / 30 |
| Llama3.1 | 13 / 6 | 0 / 2 | 27 / 28 |

These counts do not establish a safety ranking or a uniform prompt-only benefit.
Qwen's prompt-only contaminated outputs include29 denials; Gemma's corresponding
outputs include18 safe but incomplete date subsets. Neutral baseline violations
must remain separate from contamination-induced errors. Complete framing pairs
and their missingness are reported; no confirmatory significance claim is made.

The supplied structured-grant gate has zero observed unauthorized commits for
704 valid proposals, with64 unknown proposals retained. This is deterministic
enforcement conformance on the same proposals, not semantic grant extraction.

## Scope retained

The48 instances share16 construction templates. Note style and date vary
together; model blocks have fixed order. Four local Q4_K_M checkpoints cover
different families and sizes (7.2B–9B metadata), not independent providers.
SQLite records scheduling metadata only: no callback, native tool or autonomous
multi-turn trajectory runs. No public-source holdout, prevalence, arbitrary
provider/model robustness or confirmation-dialogue claim follows. Do not pool
this changed corpus/interface with the earlier v1 experiment.

## SHA-256 bindings

- Protocol: `0e8f9e2ce34be6596f91b31593f2fc7ea872d1ce01cba92bbab5fd93bfc1d86c`
- Runner: `ff29f7cfe27573bd06f9b202eb33114a0b7e92fd14b52f7d8a8fd003e9b25897`
- Auditor: `07b876eaaf207bd29496ae51ec1dd1e3133e64669c7e4b4e0057a9c0d4a05d93`
- Calibration raw: `a84e4f3fe1102c5182185fccb6d7eac7712d7946b2ac3899856d5171320c9cf3`
- Main raw: `8d45f950113dd5bd43c6d678a3a18719e2becb5e0d321561938c517d4bb00572`
- Registry: `4336e861fa26403d3a15038ab81945000aa918856fca45b359fb2171a3598d34`
- Summary CSV: `661797ad3ff86b850b1459b3ce534f96bc3a76a2eee860df34aeeb4789a80257`
- By-grant CSV: `0e8097583de1790df25615c6b100a740227bc4b07de92f91e4b34c3f69c5e821`

Main report: `analysis/local_persistence_expansion_20261011_v2.md`.
Run artifacts: `tmp/local-persistence-expansion-20261011-v2/`.
