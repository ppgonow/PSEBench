# INFOCOM native template-cluster reanalysis (2026-07-19)

## Reason

The frozen adaptive native manifest contains 80 scenario IDs per alias, but its
generator uses five semantic attack templates per boundary and instantiates each
template four times with a distinct identifier or recipient target. Treating all
80 IDs as independent semantic attacks would understate uncertainty. No raw row,
scenario, model response, branch outcome, or ledger record was changed.

## Corrected inference unit

The public `analysis/analyze_adaptive_native_templates.py` maps the 320 native
instances across four aliases to 80 alias--template clusters. For each cluster,
ASR support means that at least one of its four instantiations commits an
unauthorized effect. Same-template permissive/IACG support is compared with a
two-sided exact McNemar test. Instance ASR and TCR remain descriptive execution
counts.

| Requested alias | Instance ASR P/I | Template support P/I | Exact paired p |
| --- | ---: | ---: | ---: |
| GPT-5.5 | 2/80 vs. 0/80 | 1/20 vs. 0/20 | 1 |
| Grok-4.5 | 35/80 vs. 0/80 | 9/20 vs. 0/20 | 0.00390625 |
| GPT-5.4 | 19/79 vs. 0/79 | 7/20 vs. 0/20 | 0.015625 |
| GPT-5.6-sol | 4/80 vs. 0/80 | 3/20 vs. 0/20 | 0.25 |

For Grok-4.5, the Wilson 95% intervals on template support are
`[0.258195, 0.657918]` for permissive and `[0, 0.161130]` for IACG. The
correction preserves the strong Grok and GPT-5.4 directions while removing
pseudoreplication-driven instance-level significance claims.

## Reproduction

```bash
python3 analysis/analyze_adaptive_native_templates.py \
  --manifest scenarios/adaptive-native-holdout/MANIFEST.csv \
  --final \
    analysis/adaptive_native_fork_schema_neutral_final.jsonl \
    analysis/adaptive_native_fork_gpt54_gpt56_final.jsonl \
  --output-prefix analysis/adaptive_native_templates
```

The sanity gate regenerates and byte-compares both CSV outputs. The INFOCOM
claim audit checks the cluster count, instance count, per-alias template support,
paired p-values, and corresponding manuscript language.
