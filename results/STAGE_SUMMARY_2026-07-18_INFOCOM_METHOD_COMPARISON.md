# INFOCOM candidate-action method comparison (2026-07-18)

## Scope

This no-API experiment compares eight policies over the same 135 PSEBench
candidate-action scenarios, including 110 attack scenarios. It produces 1,080
deterministic policy/scenario rows. Supplying the candidate action isolates the
action-policy boundary from model proposal behavior.

The RTBAS/IFC-style, PAuth-style, and PCAS-style rows are typed method-family
adaptations. They are not official implementations, live model runs, or a SOTA
leaderboard. Task Shield-style and Prompt Flow Integrity-style enforcement are
reported separately on the 100-case held-out typed replay in the main paper.
PCAS-style is an internal shorthand for the declarative policy-compilation
authorization adaptation motivated by FORGE, not the name of an official system.

## Results

| Method | Evidence type | ASR | TCR | Confirmations |
|---|---|---:|---:|---:|
| Permissive | direct baseline | 110/110 | 135/135 | 0/135 |
| Firewall | direct baseline | 0/110 | 119/135 | 0/135 |
| Confirm-all | direct baseline | 0/110 | 119/135 | 126/135 |
| SLC | direct baseline | 1/110 | 135/135 | 0/135 |
| RTBAS/IFC-style | typed adaptation | 0/110 | 135/135 | 110/135 |
| PAuth-style | typed adaptation | 0/110 | 135/135 | 0/135 |
| PCAS-style | typed adaptation | 0/110 | 135/135 | 0/135 |
| IACG | reference monitor | 0/110 | 135/135 | 0/135 |

The closest task-scoped and declarative adaptations tie IACG on this supplied-
effect abstraction. The defensible conclusion is therefore not that IACG
outperforms related authorization monitors. The matrix instead quantifies the
cost of coarse alternatives: firewall and confirm-all lose 16 tasks,
confirm-all requests 126 confirmations, and untrusted-dependency confirmation
requests 110. PSEBench's distinct contribution is the committed-effect
evaluation unit, shared-proposal execution, and commit-bound receipt path.

## Reproduction

```bash
python3 analysis/run_method_comparison.py \
  --output-dir tmp/method_comparison \
  --output-label candidate_action
```

The command regenerates the released detail, overall, by-slice, and Markdown
outputs under `analysis/method_comparison_*`. `scripts/sanity_check.sh` requires
all four regenerated files to byte-match the released versions, and the INFOCOM
claim audit checks every main-paper table row.
