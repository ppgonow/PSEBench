# INFOCOM Fresh Non-Cron Authorization Utility (2026-07-15)

## Scope

This local replay extends the frozen authorization-utility design to file and
calendar effects. Each tool contributes 20 covered legitimate requests, 20
novel legitimate requests, and 20 ambiguous requests with an injected durable
upgrade, for 120 distinct scenarios total. All prompts avoid the original
intent cue table, and the frozen authorization-rule SHA-256 is recorded with
the corpus.

## IACG results

| tool | runtime condition | known legitimate TCR | novel legitimate TCR | ambiguous ASR | ambiguous TCR |
|---|---|---:|---:|---:|---:|
| file | lexical + deny | 0/20 | 0/20 | 0/20 | 20/20 |
| file | semantic-rule + deny | 20/20 | 0/20 | 0/20 | 20/20 |
| file | semantic-rule + confirm | 20/20 | 20/20 | 0/20 | 20/20 |
| calendar | lexical + deny | 0/20 | 0/20 | 0/20 | 20/20 |
| calendar | semantic-rule + deny | 20/20 | 0/20 | 0/20 | 20/20 |
| calendar | semantic-rule + confirm | 20/20 | 20/20 | 0/20 | 20/20 |

The result reproduces the cron authorization boundary on two non-cron effect
types. It also reproduces the parser limitation: frozen semantic rules cover
known constructions, while novel durable intent requires confirmation. This
is action-layer evidence and does not claim live file/calendar execution.

## Updated local overhead

The policy microbenchmark now covers 758 scenario prompts with 395 loops and
seven repeats per policy:

| policy | median microseconds | p95 microseconds |
|---|---:|---:|
| allow-only | 0.051 | 0.052 |
| confirm-all-persistent | 0.074 | 0.076 |
| SLC | 1.123 | 1.139 |
| lexical IACG | 11.493 | 11.571 |
| semantic-rule IACG | 21.507 | 22.031 |

The paraphrase-oriented rules approximately double local policy-check latency;
the path remains about 22 microseconds at p95 and excludes external tool or
model latency.

## Reproduction

```bash
python3 runner/generate_noncron_authorization_holdout.py --count-per-cell 20
python3 runner/replay_action_boundary.py \
  --scenario-dir scenarios/fresh-noncron-authorization-heldout \
  --output-root results/fresh_noncron_semantic_denied \
  --authorization-mode semantic --confirmation-mode deny
python3 runner/replay_action_boundary.py \
  --scenario-dir scenarios/fresh-noncron-authorization-heldout \
  --output-root results/fresh_noncron_semantic_confirmed \
  --authorization-mode semantic --confirmation-mode approve-ground-truth
python3 analysis/benchmark_guard_overhead.py
```

Derived outputs are under `analysis/fresh_noncron_*` and
`analysis/iacg_overhead_{summary,runs}.csv`.
