# INFOCOM Headline Claim Audit (2026-07-15)

## Scope

`analysis/infocom_claim_audit.py` reconstructs the submission's quantitative
headline claims from frozen stage records, derived CSVs, scenario manifests,
and Wilson recomputation. When the local paper source is present, it also
requires each reconstructed table row or narrative fragment to appear in
`src/sections/evaluation.tex`.

The 61 audited claims cover:

- all evidence-tier sizes in Table I;
- the original 141-run/45-scenario descriptive inventory, its explicit
  non-independence boundary, and the unique-scenario paired reference-monitor
  rows;
- held-out attack, decision-only and native-tool model, same-tool
  authorization, frozen authorization, non-cron utility, multi-tool, and
  localhost HTTP/SQLite commit-binding rows;
- policy and commit-lifecycle overhead plus all headline Wilson intervals;
- authorization utility, staged/SLC stress, artifact-oracle coverage, blinded
  label audit, gateway retries, and native primary-effect/confirmation counts.

## Result

```text
claims=61 paper_checked=61 failures=0
```

The detailed source-to-claim mapping is
`analysis/infocom_claim_audit.csv`. Every audited manuscript number matches its
released source.

## Reproduction

```bash
python3 analysis/independent_unit_analysis.py
python3 analysis/infocom_claim_audit.py
```

The command is part of `scripts/sanity_check.sh`. In the anonymous artifact,
paper sources are intentionally absent, so the same command validates all data
invariants and records paper checks as `not_checked`; the local submission
workspace performs both layers.

## Boundary

This audit checks quantitative provenance and exact manuscript placement. It
does not validate the semantic correctness of citations, replace raw external
model execution, or establish that a derived benchmark slice is representative
of all agent workflows.
