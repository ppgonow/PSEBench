# INFOCOM same-tool cluster-analysis amendment (2026-07-21)

## Timing and scope

This amendment was written after the four-alias formal run had started. It does
not change the frozen scenarios, prompts, model aliases, runner, request
parameters, policies, commit bridge, or final-row retention rules. No scenario
is rerun, removed, replaced, or selected because of this amendment.

## Motivation

The formal corpus contains 48 workflow-specific templates, paired across clean
and injected exposure. A structural audit noted that the four workflows reuse
12 carrier/style positions. Treating all 48 pairs as completely unstructured
language samples could therefore understate dependence across parallel styles.

## Added analyses

The pre-specified same-template comparisons remain the primary analysis:

- 48 clean/injected pairs per alias;
- 48 permissive/IACG injected pairs per alias;
- exact two-sided McNemar tests.

Two additional outputs are added:

1. `exposure_paired`: same-template clean versus injected comparisons for the
   first proposal, branch ASR, and branch TCR;
2. `cluster_paired`: exact two-sided sign-flip sensitivity tests over 12
   carrier/style blocks, where each block contains the four workflows.

The block analysis is post-hoc and conservative. It will be reported as a
sensitivity analysis rather than substituted for the frozen primary result.
Both significant and null outcomes will be retained.

## Implementation boundary

Only `analysis/summarize_same_tool_native_commit.py` and its unit tests change.
Raw attempts, final JSONL records, ledgers, scenario hashes, and model requests
remain untouched.
