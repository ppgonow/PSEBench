# INFOCOM Confirmation-Framing Analysis Plan (2026-07-15)

## Purpose

This plan is frozen before any confirmation-framing API request. It prevents a
small supporting experiment from being interpreted with a post hoc statistical
test or from treating non-significance as evidence that contaminated framing is
safe.

## Endpoints and Pairing

Each scenario is evaluated under `neutral` and `contaminated` confirmation
framing for each model. The same scenario ID forms a pair. The two endpoints
are analyzed separately:

1. attack false approval: approval on the 10 attack scenarios per model;
2. legitimate approval: approval on the 10 benign scenarios per model.

For every model/endpoint, the report includes neutral and contaminated rates,
the contaminated-minus-neutral risk difference, both discordant counts, and a
two-sided exact McNemar test. The six model/endpoint p-values receive Holm
family-wise correction. Per-cell Wilson intervals remain descriptive.

## Power Result

The planned 20 scenarios give only 10 pairs per endpoint per model. Under the
most favorable alternative, where every discordance moves only in the harmful
direction, six concordant directional changes are needed for unadjusted
`p<=0.05`, seven for a three-model primary endpoint, and eight for six-test
Bonferroni sensitivity. With 10 pairs and a true 0.30 harmful shift, exact power
is only 0.047 unadjusted, 0.011 at `0.05/3`, and 0.002 at `0.05/6`. Even a 0.50
shift has only 0.377, 0.172, and 0.055 power, respectively.

Therefore the bounded 120-call matrix is a descriptive pilot and interface
robustness check, not a powered equivalence or no-effect study. A non-significant
McNemar result must not be written as evidence that contaminated rationale has
no impact.

## Expansion Trade-off

For a primary attack endpoint across three models (`alpha=0.05/3`), 20 attack
pairs per model require 240 total balanced-matrix calls and provide only 0.392
power for a 0.30 shift. Thirty attack pairs per model require 360 calls and
provide 0.840 power. Testing both endpoints as six confirmatory hypotheses is
more demanding: 30 pairs provide 0.719 power for a 0.30 shift, while 40 pairs
require 480 calls and provide 0.945 power.

Given the supporting role of this experiment, endpoint cost, and rate-limit
risk, the current plan remains 120 calls. Any expansion must be declared before
examining outcome differences and use a new run ID; it must not be triggered by
which model or framing appears favorable.

## Reproduction

```bash
python3 analysis/confirmation_power_analysis.py

python3 analysis/summarize_confirmation_decision.py \
  results/confirmation_decision/infocom-confirmation20_raw.jsonl \
  --output analysis/infocom_confirmation20_summary.csv \
  --paired-output analysis/infocom_confirmation20_paired.csv \
  --expected-models gpt-5.4 gpt-5.5 gpt-5.6-sol
```

The derived planning tables are `analysis/confirmation_power.csv` and
`analysis/confirmation_precision.csv`. No model or external service is called
by the planning script or summarizer.
