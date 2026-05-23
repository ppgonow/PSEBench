# PSEBench

PSEBench is a benchmark and measurement pipeline for studying security failures in tool-using agent frameworks, with a current emphasis on persistence escalation and authorization-aware action-boundary mediation.

It is designed to answer questions like:
- When can untrusted text induce higher-scope tool actions?
- How often do attacks succeed under different runner and mediation policies?
- Which action-boundary policies preserve utility while blocking unauthorized persistence?

## Current focus
- hybrid tasks where the user legitimately needs tools, but injected content tries to escalate a one-shot action into a persistent, recurring, or broader-scope action
- message -> cron -> persistence
- implicit vs. explicit persistence intent
- recipient broadening and related authorization-boundary violations
- tool-layer policies including IACG, confirm-all-persistent, SLC, and firewall-style baselines

## Threat model
### Untrusted input sources
- Web: page body, comments, and hidden content
- Message: IM/chat/email-like inbound text
- File: workspace documents with embedded instructions

### High-risk actions
- persistence or recurrence creation
- recipient broadening or redirection
- message exfiltration
- command execution
- sensitive device actions such as camera, screen, or location

### Attacker capability
The attacker controls only content, not framework internals or runner configuration.

## Public repository contents
- `scenarios/` — benchmark scenario YAMLs and schema
- `runner/` — execution harnesses and runner notes
- `analysis/` — aggregation scripts and exported summary tables
- `oracles/` — manual labeling helpers and oracle conventions
- `results/` — public stage summaries
- `data/web/` — tracked benign and attack web fixtures used by the benchmark
- `ARTIFACT_MANIFEST.md` — public artifact scope, reproduction tiers, and excluded local-only material

Paper drafts, slide decks, imported external corpora, local notes, and machine-specific config are intentionally kept out of the public snapshot.

## Representative outputs
- `analysis/main_table_by_family_plus_persistent.md`
- `analysis/new_baseline_comparison_table.csv`
- `analysis/prompt_only_baseline_summary.csv`
- `analysis/oracle_coverage_summary.csv`
- `analysis/artifact_oracle_coverage_summary.csv`
- `analysis/noncron_replication_summary.csv`
- `analysis/iacg_overhead_summary.csv`
- `results/STAGE_SUMMARY_CONFIRM_ALL_PERSISTENT.md`
- `results/STAGE_SUMMARY_SLC.md`
- `results/STAGE_SUMMARY_NEW_BASELINES.md`

## Local configuration
If you need machine-specific target mappings or local honeypot paths, create a private runner config from the example template:

```bash
cp runner/config.example.yaml runner/config.yaml
```

`runner/config.yaml` is gitignored and not included in the public repo.

## Reproducibility
See:
- `ARTIFACT_MANIFEST.md`
- `REPRODUCIBILITY.md`
- `runner/README.md`
- `REPO_MAP.md`
