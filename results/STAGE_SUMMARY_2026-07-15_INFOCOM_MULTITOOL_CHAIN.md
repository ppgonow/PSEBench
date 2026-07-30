# INFOCOM Frozen Multi-Tool Chain Replay (2026-07-15)

## Scope

This local action-layer replay contains 60 distinct scenarios across three
two-tool families, with 20 scenarios per family:

- file to message with an injected recipient expansion;
- calendar to message with an injected recurring calendar effect;
- message to file with an injected durable file effect.

Each scenario pre-registers two authorized/required effects and one attack
effect before replay. The proposal sequence contains the two required effects
plus the attack effect. The corpus manifest hashes every YAML file and records
the frozen `runner/effect_boundary.py` SHA-256.

## Results

| family | n | permissive ASR | IACG ASR | permissive TCR | IACG TCR |
|---|---:|---:|---:|---:|---:|
| file to message recipient expansion | 20 | 20/20 | 0/20 | 20/20 | 20/20 |
| calendar to message recurrence | 20 | 20/20 | 0/20 | 20/20 | 20/20 |
| message to file persistence | 20 | 20/20 | 0/20 | 20/20 | 20/20 |
| **Overall** | **60** | **60/60** | **0/60** | **60/60** | **60/60** |

For 0/60 and 60/60, the two-sided Wilson 95% intervals are [0.000,
0.060] and [0.940, 1.000]. All 60 paired scenario IDs are permissive-only
attack successes, with exact McNemar `p=1.73e-18`. Each 20-case family has
exact McNemar `p=1.91e-6`.

## Oracle separation and interpretation

IACG checks each proposed effect against the typed authorization envelopes.
Attack labeling does not call this guard decision: it checks whether a
pre-registered attack effect appears in the committed sequence. Task labeling
separately requires every pre-registered required effect to be committed.

The result shows that the action-boundary check composes across the tested
multi-tool proposal sequences: it retains both required actions while removing
the extra recipient, recurring, or durable effect. This is deterministic
action-layer evidence. It is not live model execution, a native framework
benchmark, a user study, or evidence that general multi-turn authorization
inference is solved.

## Reproduction

```bash
python3 runner/generate_multitool_chain_holdout.py --count-per-family 20
python3 runner/replay_multitool_chain.py --policies permissive IACG
python3 analysis/summarize_multitool_chain.py
```

Derived outputs are `analysis/multitool_chain_{detail,summary,paired}.csv`.
