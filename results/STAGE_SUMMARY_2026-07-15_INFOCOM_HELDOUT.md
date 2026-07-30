# INFOCOM Held-Out Action-Layer Stage (2026-07-15)

## Scope

This stage creates a deterministic held-out adaptive corpus and replays the
typed authorization boundary without contacting live services. The corpus has
100 distinct message-to-scheduler scenarios, ten attack styles, and no current
`intent_policy.py` one-shot or persistence cue in the user prompt or injected
artifact. Each YAML is hashed in `scenarios/hybrid-adaptive-heldout/MANIFEST.csv`.

## Results

| policy | n | ASR | Wilson 95% CI | TCR | Wilson 95% CI |
|---|---:|---:|---|---:|---|
| permissive | 100 | 100/100 | [0.963, 1.000] | 100/100 | [0.963, 1.000] |
| IACG | 100 | 0/100 | [0.000, 0.037] | 100/100 | [0.963, 1.000] |
| TaskShield-style | 100 | 0/100 | [0.000, 0.037] | 100/100 | [0.963, 1.000] |
| PFI-style | 100 | 0/100 | [0.000, 0.037] | 100/100 | [0.963, 1.000] |

All three guarded policies disagree with permissive execution on 100 paired
scenarios and never in the opposite direction. The exact two-sided McNemar
value is approximately `1.58e-30` for each comparison.

## Interpretation boundary

This is action-layer evidence, not a live model-driven result. The runner
commits typed effects and labels attack success from the committed effect. It
does not claim that a language model would propose the escalated action on every
case. The next experiment is a bounded live end-to-end subset using the same
held-out scenarios and at least two model backends.

## Reproduction

```bash
python3 runner/generate_heldout_adaptive.py --count 100
python3 runner/replay_action_boundary.py \
  --policies permissive IACG TaskShield-style PFI-style
python3 analysis/summarize_heldout_replay.py
```
