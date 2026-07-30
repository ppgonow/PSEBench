# INFOCOM Authorization-Utility Follow-up (2026-07-15)

## Scope

This follow-up reruns the same 150 scenario IDs from the authorization-utility
stage under two controlled changes:

- `confirmation=approve-ground-truth`: a bounded replay protocol in which a
  confirmation approves a proposed effect only when it remains inside the
  ground-truth envelope. An injected recurring upgrade is denied and falls
  back to the safe one-shot task.
- `authorization=semantic`: a small, deterministic paraphrase-oriented rule
  adaptation that recognizes re-arming, retention, requeueing, and standing
  schedules. It is not a learned semantic model and is not presented as a
  general semantic reasoner.

All runs remain local action-layer replays. No cron, message service, model
endpoint, or external credential was used.

## IACG utility matrix

| condition | legitimate persistence TCR | legitimate false-block | legitimate confirmation | ambiguous attack ASR | ambiguous attack TCR |
|---|---:|---:|---:|---:|---:|
| lexical + deny | 0/100 | 100/100 | 100/100 | 0/50 | 50/50 |
| lexical + approve-ground-truth | 100/100 | 0/100 | 100/100 | 0/50 | 50/50 |
| semantic + deny | 100/100 | 0/100 | 0/100 | 0/50 | 50/50 |
| semantic + approve-ground-truth | 100/100 | 0/100 | 0/100 | 0/50 | 50/50 |

For the 0/50 attack rates, the Wilson 95% upper bound is 0.071. For 50/50
attack-side TCR the Wilson interval is [0.929, 1.000], and for 100/100
legitimate TCR it is [0.963, 1.000]. Each guarded policy has 50 baseline-only
attack successes and no reverse discordant pair against permissive execution;
the paired exact McNemar value is `1.78e-15`.

The other policy adaptations show the expected tradeoff. Under the semantic
condition, TaskShield-style also completes 100/100 legitimate persistence
requests, while confirm-all-persistent remains 0/100 without confirmation and
100/100 after confirmation. PFI-style completes 100/100 in all four local
conditions because its adaptation gates untrusted provenance rather than
ambiguous user wording.

## Interpretation

The new evidence distinguishes two sources of utility loss:

1. Without a confirmation response, a conservative lexical parser protects the
   boundary but cannot complete an implicitly authorized durable task.
2. A bounded confirmation response restores utility without approving the
   injected escalation.
3. A small paraphrase-aware authorization adaptation removes the false-block
   on this held-out corpus without increasing attack success.

The third result is a controlled rule-adaptation result, not evidence that a
general language model semantic parser is solved. The paper should report the
parser limitation and confirmation burden explicitly, then use this matrix as
motivation for future learned authorization inference rather than as a broad
claim of semantic coverage.

## Reproduction

```bash
python3 runner/replay_action_boundary.py \
  --scenario-dir scenarios/authorization-utility-heldout \
  --output-root results/authorization_utility_lexical_confirmed \
  --authorization-mode lexical \
  --confirmation-mode approve-ground-truth
python3 runner/replay_action_boundary.py \
  --scenario-dir scenarios/authorization-utility-heldout \
  --output-root results/authorization_utility_semantic_denied \
  --authorization-mode semantic \
  --confirmation-mode deny
python3 runner/replay_action_boundary.py \
  --scenario-dir scenarios/authorization-utility-heldout \
  --output-root results/authorization_utility_semantic_confirmed \
  --authorization-mode semantic \
  --confirmation-mode approve-ground-truth

python3 analysis/summarize_heldout_replay.py \
  --root results/authorization_utility_lexical_confirmed \
  --output-prefix analysis/authorization_utility_lexical_confirmed
python3 analysis/summarize_heldout_replay.py \
  --root results/authorization_utility_semantic_denied \
  --output-prefix analysis/authorization_utility_semantic_denied
python3 analysis/summarize_heldout_replay.py \
  --root results/authorization_utility_semantic_confirmed \
  --output-prefix analysis/authorization_utility_semantic_confirmed
```
