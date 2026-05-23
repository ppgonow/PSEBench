# Repository Map

## Top-level directories
- `analysis/` — aggregation scripts and exported CSV/Markdown tables
- `data/` — local data area plus tracked web fixtures under `data/web/`
- `oracles/` — oracle notes and manual labeling helpers
- `results/` — public stage summaries; raw run artifacts under `results/runs/` stay gitignored
- `runner/` — benchmark runners and harness scripts
- `scenarios/` — benchmark scenarios grouped by family and slice
- `tests/` — no-credential unit checks for guard policy behavior

## Important files
- `ARTIFACT_MANIFEST.md` — public artifact scope and reproduction tiers
- `README.md` — project overview and public repository scope
- `REPRODUCIBILITY.md` — representative reproduction commands
- `runner/README.md` — runner-specific notes
- `runner/config.example.yaml` — template for machine-local runner configuration
- `data/README.md` — notes on tracked versus local-only data

## Key experimental slices
- `scenarios/hybrid/` — core cron matched slice
- `scenarios/hybrid-contrast-cron/` — authorization-boundary contrast
- `scenarios/hybrid-implicit-cron/` — implicit durability slice
- `scenarios/hybrid-failure-cron/` — lexical and negation failure stress set
- `scenarios/hybrid-file/` — file persistence families
- `scenarios/hybrid-calendar/` — calendar recurrence families
- `scenarios/hybrid-msg/` — recipient broadening and hijack family
- `scenarios/hybrid-wainject/` — mapped-transfer slice inspired by external prompt-injection styles

## Representative public outputs
- `analysis/main_table_by_family_plus_persistent.md`
- `analysis/new_baseline_comparison_table.csv`
- `analysis/confirm_all_persistent_summary.csv`
- `analysis/slc_summary.csv`
- `analysis/prompt_only_baseline_summary.csv`
- `analysis/oracle_coverage_summary.csv`
- `analysis/auto_oracle_agreement_summary.csv`
- `analysis/auto_oracle_noncron_summary.csv`
- `analysis/iacg_overhead_summary.csv`
- `results/STAGE_SUMMARY_CONFIRM_ALL_PERSISTENT.md`
- `results/STAGE_SUMMARY_SLC.md`
- `results/STAGE_SUMMARY_NEW_BASELINES.md`
