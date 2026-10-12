# Receipt-Profile Composition Audit (2026-08-26)

## Scope

The existing frozen receipt experiment removes one field at a time. This
follow-up enumerates all \(2^5=32\) verification profiles over principal,
authorization version, exact effect, expiry, and confirmation nonce. It reuses
the same 150 check-to-commit scenarios, but writes separate outputs and does
not pool them with the single-field matrix.

## Results

- 4,800 profile/scenario rows: 32 profiles x 150 scenarios.
- 3,200 attack rows and 1,600 stable-control rows.
- Every profile completes all 50/50 stable controls.
- The full profile records 0/100 stale commits.
- For each invalidation family, 20/20 stale commits occur exactly when its
  matching receipt field is disabled; retaining that field yields 0/20.
- Every row produces the expected ledger cardinality: one row for an allowed
  commit and zero rows for a blocked commit.

## Interpretation

The composition audit confirms the field-to-invalidation mapping across all
combinations of omissions. It strengthens the component-necessity result but
remains a finite, dependency-free conformance construction; it is not a field
failure-rate or deployment-prevalence estimate.

## Reproduction

```bash
python3 runner/run_receipt_mask_ablation.py --overwrite
python3 analysis/audit_receipt_mask_ablation.py \
  --detail analysis/receipt_mask_ablation_detail.csv \
  --output-prefix tmp/repro_receipt_mask_ablation
```

## Artifacts

- `runner/run_receipt_mask_ablation.py`
- `analysis/audit_receipt_mask_ablation.py`
- `analysis/receipt_mask_ablation_detail.csv`
- `analysis/receipt_mask_ablation_summary.csv`
- `analysis/receipt_mask_ablation_family.csv`
- `analysis/receipt_mask_ablation_integrity.json`
