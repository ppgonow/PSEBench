# INFOCOM Authorization-Utility Stage (2026-07-15)

## Scope

This stage tests whether low attack success under IACG is obtained by
over-blocking legitimate durable requests. It adds two deterministic,
action-layer suites and does not contact live services:

- `implicit-legitimate-persistence`: 100 benign cron requests whose structured
  ground truth requires recurring state, but whose user wording contains no
  token from the current one-shot/recurring cue table.
- `ambiguous-authorization`: 50 one-shot cron tasks whose wording is
  intentionally ambiguous and whose inbound artifact attempts a recurring
  upgrade.

The replay keeps two authorization records separate. Ground-truth
authorization is used by the replay oracle, fallback simulation, and
attack/false-block labels; it is never passed to a policy decision. Runtime
authorization is inferred from the prompt using the fixed rule table. When a
one-shot attack is blocked or confirmed, the safe one-shot effect is committed
as a fallback. A legitimate recurring task that is blocked or left pending
confirmation is not marked complete.

## Results

### Ambiguous authorization (n = 50 attacks)

| policy | ASR | TCR | confirmation rate |
|---|---:|---:|---:|
| permissive | 50/50 | 50/50 | 0/50 |
| IACG | 0/50 | 50/50 | 50/50 |
| TaskShield-style | 0/50 | 50/50 | 0/50 |
| PFI-style | 0/50 | 50/50 | 0/50 |
| confirm-all-persistent | 0/50 | 50/50 | 50/50 |

### Implicit legitimate persistence (n = 100 benign tasks)

| policy | false-block rate | TCR | confirmation rate |
|---|---:|---:|---:|
| permissive | 0/100 | 100/100 | 0/100 |
| IACG | 100/100 | 0/100 | 100/100 |
| TaskShield-style | 100/100 | 0/100 | 0/100 |
| PFI-style | 0/100 | 100/100 | 0/100 |
| confirm-all-persistent | 100/100 | 0/100 | 100/100 |

For the 50 paired attack cases, permissive versus each guarded policy has
McNemar exact `p = 1.78e-15` (50 baseline-only attack successes, no reverse
discordant pairs). For the 100 paired legitimate cases, permissive versus
IACG, TaskShield-style, and confirm-all-persistent has `p = 1.58e-30` on the
task outcome; PFI-style has no task discordance.

Wilson 95% intervals and all paired comparisons are in:

- `analysis/authorization_utility_summary.csv`
- `analysis/authorization_utility_paired.csv`
- `analysis/authorization_utility_by_style.csv`
- `analysis/authorization_utility_detail.csv`

## Interpretation and next step

The security result remains strong on the ambiguous attack suite, but this
stage rejects a blanket claim that the current IACG rule table preserves all
legitimate persistence. On wording with no lexical authorization evidence,
IACG correctly refuses to silently commit durable state, but its confirmation
path has zero utility without a user response. The result is therefore a
measured security--utility tradeoff and a concrete parser limitation, not an
IACG win on every condition.

The next experiment should add a bounded confirmation-response condition and a
semantic authorization variant, then rerun the same 100/50 scenario IDs. The
variant must be evaluated against the same ground-truth labels and report
confirmation burden, false-block rate, ASR, and TCR separately. No additional
credentialed API calls are needed for this step.

## Reproduction

```bash
python3 runner/generate_authorization_utility.py \
  --legitimate-count 100 --ambiguous-count 50
python3 runner/replay_action_boundary.py \
  --scenario-dir scenarios/authorization-utility-heldout \
  --output-root results/authorization_utility_runs
python3 analysis/summarize_heldout_replay.py \
  --root results/authorization_utility_runs \
  --output-prefix analysis/authorization_utility
```

The replay is local and action-layer only; it does not execute cron, send
messages, or invoke a model endpoint.
