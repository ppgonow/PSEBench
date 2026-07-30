# INFOCOM receipt-field ablation result (2026-07-21)

## Frozen matrix

The formal local run used the pre-specified 150 commit-race scenarios and seven
policies, producing 1,050 policy/scenario rows and 1,050 unique keys. The run
completed once without selective replacement. Its ephemeral HMAC key and
temporary SQLite ledger were destroyed on process exit.

## Results

| Policy | Overall ASR | Matching-family ASR | Nonmatching ASR | TCR |
|---|---:|---:|---:|---:|
| Full receipt | 0/100 | 0/20 in every family | 0/80 | 50/50 |
| No principal | 20/100 | 20/20 principal switch | 0/80 | 50/50 |
| No authorization version | 20/100 | 20/20 revocation | 0/80 | 50/50 |
| No exact effect | 20/100 | 20/20 substitution | 0/80 | 50/50 |
| No expiry | 20/100 | 20/20 lease expiry | 0/80 | 50/50 |
| No confirmation nonce | 20/100 | 20/20 replay | 0/80 | 50/50 |
| Online reauthorization at commit | 0/100 | 0/20 in every family | 0/80 | 50/50 |

For each single-field ablation versus the full receipt, the same-ID exact
McNemar comparison has 20 comparator-only stale commits and
`p=1.9073486328125e-06`. Full receipt and online reauthorization have no
discordant attack pair (`p=1`). Overall Wilson 95% intervals are [0, 0.037] for
0/100 and [0.133, 0.289] for 20/100. Every policy completes all 50 controls.

## Integrity

- 1,050 detail rows and 1,050 unique policy/scenario keys.
- 700 attack rows and 350 control rows.
- 450 commits and exactly 450 SQLite ledger rows.
- 100 stale commits, all confined to the pre-specified matching ablation cells.
- 350/350 control tasks complete.
- The independent audit reconstructs all summaries and paired tests from the
  detail CSV.

## Interpretation

The result provides a component-level necessity argument: no one receipt field
is redundant under the frozen invalidation model. It does not show that a
receipt is the only secure design. A stronger online baseline that receives the
trusted grant and authoritative state inside the commit boundary ties the full
receipt. The defensible claim is therefore that commit-time current-authority
validation is necessary, while the authenticated receipt is IACG's delegation
mechanism for carrying the exact prior decision across the service boundary.

## Artifacts

- `analysis/receipt_field_ablation_detail.csv`
- `analysis/receipt_field_ablation_summary.csv`
- `analysis/receipt_field_ablation_paired.csv`
- `analysis/receipt_field_ablation_integrity.csv`
- `results/receipt_field_ablation/receipt_field_ablation.jsonl`
- `runner/run_receipt_field_ablation.py`
- `analysis/audit_receipt_field_ablation.py`
