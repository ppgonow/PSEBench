# INFOCOM Fresh Authorization Holdout (2026-07-15)

## Frozen design

The runtime authorization rules were frozen before this corpus was generated.
The corpus records the SHA-256 of `runner/effect_boundary.py` in
`scenarios/fresh-authorization-heldout/RULE_SNAPSHOT_SHA256.txt` and contains:

- 50 legitimate persistent requests using covered semantic compositions;
- 50 legitimate persistent requests using novel paraphrases not covered by
  either the lexical or semantic-rule table;
- 50 fresh ambiguous one-shot requests with an injected recurring upgrade.

All 150 prompts avoid the original one-shot and recurring cue vocabulary. The
generator validates the expected frozen-rule coverage class and hashes every
scenario. The rules were not changed after observing the results.

## IACG results

| runtime condition | known legitimate TCR | novel legitimate TCR | novel false-block | ambiguous ASR | ambiguous TCR |
|---|---:|---:|---:|---:|---:|
| lexical + deny | 0/50 | 0/50 | 50/50 | 0/50 | 50/50 |
| semantic-rule + deny | 50/50 | 0/50 | 50/50 | 0/50 | 50/50 |
| semantic-rule + approve-ground-truth | 50/50 | 50/50 | 0/50 | 0/50 | 50/50 |

For 0/50 ASR the Wilson 95% interval is [0.000, 0.071]. For 50/50
task completion the interval is [0.929, 1.000].

## Interpretation

The fresh split rejects a broad semantic-generalization claim. The frozen
semantic-rule adaptation generalizes across new topics and instances of its
covered constructions, but not to genuinely novel paraphrases. The bounded
confirmation protocol supplies the missing open-vocabulary fallback: it
restores all 50 novel legitimate tasks without approving any of the 50
injected recurring upgrades.

The defensible INFOCOM claim is therefore a layered one: typed effect
enforcement prevents silent escalation; deterministic authorization inference
handles known explicit and paraphrased intent; and unresolved durable intent
requires confirmation. This experiment is a local action-layer replay, not a
learned semantic parser, live user study, or live tool execution.

## Reproduction

```bash
python3 runner/generate_fresh_authorization_holdout.py \
  --known-count 50 --novel-count 50 --ambiguous-count 50
python3 runner/replay_action_boundary.py \
  --scenario-dir scenarios/fresh-authorization-heldout \
  --output-root results/fresh_authorization_semantic_denied \
  --authorization-mode semantic --confirmation-mode deny
python3 runner/replay_action_boundary.py \
  --scenario-dir scenarios/fresh-authorization-heldout \
  --output-root results/fresh_authorization_semantic_confirmed \
  --authorization-mode semantic --confirmation-mode approve-ground-truth
```

Derived summaries are written to
`analysis/fresh_authorization_{lexical_denied,semantic_denied,semantic_confirmed}_*.csv`.
