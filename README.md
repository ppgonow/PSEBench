# PSEBench

PSEBench is a benchmark and measurement pipeline for studying security failures in tool-using agent frameworks, with a current emphasis on persistence escalation and authorization-aware action-boundary mediation. Manuscript sources and venue-specific submission metadata are kept outside this artifact.

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

For double-blind review, use an anonymized mirror/archive rather than a URL that reveals author identity through the hosting account. See `ANONYMIZATION.md`.

## Representative outputs
- `analysis/main_table_by_family_plus_persistent.md`
- `analysis/independent_unit_inventory.csv`
- `analysis/independent_paired_outcomes.csv`
- `analysis/independent_paired_primary.csv`
- `analysis/new_baseline_comparison_table.csv`
- `analysis/prompt_only_baseline_summary.csv`
- `analysis/oracle_coverage_summary.csv`
- `analysis/artifact_oracle_coverage_summary.csv`
- `analysis/noncron_replication_summary.csv`
- `analysis/cross_model_combined_balanced72_overall.csv`
- `analysis/label_audit_agreement_summary.csv`
- `analysis/iacg_overhead_summary.csv`
- `analysis/http_commit_race_summary.csv`
- `analysis/http_commit_race_paired.csv`
- `analysis/multiprocess_commit_race_summary.csv`
- `analysis/multiprocess_commit_race_paired.csv`
- `analysis/commit_gateway_load_detail.csv`
- `analysis/commit_gateway_load_summary.csv`
- `analysis/audit_commit_gateway_load.py`
- `analysis/network_schedule_detail.csv`
- `analysis/network_schedule_summary.csv`
- `analysis/network_schedule_inference.csv`
- `analysis/network_schedule_by_family.csv`
- `analysis/network_schedule_paired.csv`
- `analysis/audit_network_schedule.py`
- `analysis/analyze_network_schedule_results.py`
- `analysis/async_queue_commit_detail.csv`
- `analysis/async_queue_commit_summary.csv`
- `analysis/async_queue_commit_integrity.csv`
- `analysis/audit_async_queue_commit.py`
- `analysis/docker_queue_failover_detail.csv`
- `analysis/docker_queue_failover_summary.csv`
- `analysis/docker_queue_failover_integrity.csv`
- `analysis/docker_queue_failover_metadata.csv`
- `analysis/audit_docker_queue_failover.py`
- `analysis/make_figure1_v2.py`
- `analysis/service_integrated_commit_detail.csv`
- `analysis/service_integrated_commit_summary.csv`
- `analysis/service_integrated_commit_integrity.csv`
- `analysis/audit_service_integrated_commit.py`
- `analysis/postgres_integrated_commit_detail.csv`
- `analysis/postgres_integrated_commit_summary.csv`
- `analysis/postgres_integrated_commit_integrity.csv`
- `analysis/postgres_integrated_commit_metadata.csv`
- `analysis/audit_postgres_integrated_commit.py`
- `analysis/container_commit_race_summary.csv`
- `analysis/container_commit_race_paired.csv`
- `analysis/container_commit_race_topology.csv`
- `analysis/multihost_commit_race_summary.csv`
- `analysis/multihost_commit_race_paired.csv`
- `analysis/multihost_commit_race_topology.csv`
- `analysis/multihost_commit_race_audit_integrity.csv`
- `scenarios/native-e2e48/MANIFEST.csv`
- `runner/run_native_e2e.py`
- `analysis/summarize_native_e2e.py`
- `analysis/native_e2e48_final.jsonl`
- `analysis/native_e2e48_summary.csv`
- `analysis/native_e2e48_paired.csv`
- `analysis/native_e2e48_attempt_audit.csv`
- `scenarios/adaptive-native-holdout/MANIFEST.csv`
- `runner/run_adaptive_native_fork.py`
- `analysis/summarize_adaptive_native_fork.py`
- `analysis/audit_adaptive_native_fork.py`
- `analysis/adaptive_native_fork_holdout_final.jsonl`
- `analysis/adaptive_native_fork_holdout_summary.csv`
- `analysis/adaptive_native_fork_holdout_postrun_audit_by_boundary.csv`
- `analysis/adaptive_native_fork_holdout_postrun_audit_ledger.csv`
- `analysis/adaptive_native_fork_holdout_postrun_audit_paired.csv`
- `analysis/adaptive_native_fork_schema_neutral_final.jsonl`
- `analysis/adaptive_native_fork_schema_neutral_summary.csv`
- `analysis/adaptive_native_fork_schema_neutral_paired.csv`
- `analysis/adaptive_native_fork_schema_neutral_postrun_audit_by_boundary.csv`
- `analysis/adaptive_native_fork_schema_neutral_postrun_audit_ledger.csv`
- `analysis/adaptive_native_fork_schema_neutral_postrun_audit_paired.csv`
- `analysis/analyze_adaptive_native_templates.py`
- `analysis/adaptive_native_templates_detail.csv`
- `analysis/adaptive_native_templates_summary.csv`
- `scenarios/adapter-observer-heldout/corpus.json`
- `runner/same_tool_observer.py`
- `analysis/audit_adapter_observer_holdout.py`
- `analysis/adapter_observer_holdout_detail.csv`
- `analysis/adapter_observer_holdout_summary.csv`
- `analysis/adapter_observer_holdout_coverage.csv`
- `analysis/adapter_observer_holdout_integrity.csv`
- `scenarios/posix-file-provider-heldout/corpus.json`
- `runner/posix_file_service.py`
- `runner/generate_posix_file_provider_holdout.py`
- `analysis/audit_posix_file_provider.py`
- `analysis/posix_file_provider_summary.csv`
- `analysis/posix_file_provider_integrity.csv`
- `scenarios/caldav-provider-heldout/corpus.json`
- `runner/radicale_caldav_service.py`
- `runner/generate_caldav_provider_holdout.py`
- `analysis/audit_caldav_provider.py`
- `analysis/caldav_provider_summary.csv`
- `analysis/caldav_provider_integrity.json`
- `analysis/native_extension_protocol_v1.md`
- `analysis/audit_native_extension.py`
- `analysis/native_extension_grok_4_6_integrity.json`
- `formal/bounded_security_model.py`
- `formal/bounded_oracle_lattice.py`
- `formal/bounded_multi_principal_authority.py`
- `analysis/audit_feedback_adaptive_v2.py`
- `scenarios/same-tool-native-holdout/MANIFEST.csv`
- `scenarios/same-tool-normalization/conformance.json`
- `runner/run_same_tool_native_commit.py`
- `analysis/summarize_same_tool_native_commit.py`
- `analysis/same_tool_native_commit_summary.csv`
- `analysis/same_tool_native_commit_paired.csv`
- `analysis/same_tool_native_commit_exposure_paired.csv`
- `analysis/same_tool_native_commit_cluster_paired.csv`
- `analysis/same_tool_native_commit_cluster_bootstrap.csv`
- `analysis/same_tool_native_commit_multiplicity.csv`
- `analysis/same_tool_native_commit_precision.csv`
- `analysis/same_tool_native_commit_commit_summary.csv`
- `analysis/same_tool_native_commit_integrity.csv`
- `runner/strict_effects_v2.py`
- `analysis/audit_adaptive_effect_v2.py`
- `analysis/adaptive_effect_v2_detail.csv`
- `analysis/adaptive_effect_v2_summary.csv`
- `analysis/adaptive_effect_v2_integrity.csv`
- `analysis/audit_benchmark_oracle_capabilities.py`
- `analysis/benchmark_oracle_capability_audit.csv`
- `analysis/benchmark_oracle_capability_task_inventory.csv`
- `analysis/benchmark_oracle_capability_integrity.csv`
- `scenarios/oracle-distinguishability/official_agentdojo_v1.json`
- `analysis/audit_official_oracle_distinguishability.py`
- `analysis/official_oracle_distinguishability_detail.csv`
- `analysis/official_oracle_distinguishability_summary.csv`
- `analysis/official_oracle_distinguishability_integrity.csv`
- `runner/run_native_service_commit_bridge.py`
- `analysis/audit_native_service_commit_bridge.py`
- `results/native_service_commit_bridge/native_service_commit_bridge.jsonl`
- `analysis/native_service_commit_bridge_detail.csv`
- `analysis/native_service_commit_bridge_summary.csv`
- `analysis/native_service_commit_bridge_paired.csv`
- `analysis/native_service_commit_bridge_integrity.csv`
- `analysis/native_service_commit_bridge_topology.csv`
- `analysis/native_service_commit_bridge_audit.csv`
- `analysis/audit_same_tool_normalization.py`
- `analysis/same_tool_normalization_summary.csv`
- `analysis/same_tool_normalization_integrity.csv`
- `runner/run_receipt_field_ablation.py`
- `analysis/audit_receipt_field_ablation.py`
- `analysis/receipt_field_ablation_summary.csv`
- `analysis/receipt_field_ablation_paired.csv`
- `analysis/receipt_field_ablation_integrity.csv`
- `runner/run_receipt_mask_ablation.py`
- `analysis/audit_receipt_mask_ablation.py`
- `analysis/receipt_mask_ablation_summary.csv`
- `analysis/receipt_mask_ablation_family.csv`
- `analysis/receipt_mask_ablation_integrity.json`
- `results/STAGE_SUMMARY_CONFIRM_ALL_PERSISTENT.md`
- `results/STAGE_SUMMARY_SLC.md`
- `results/STAGE_SUMMARY_NEW_BASELINES.md`

## Local configuration
If you need machine-specific target mappings or local honeypot paths, create a private runner config from the example template:

```bash
cp runner/config.example.yaml runner/config.yaml
```

`runner/config.yaml` is gitignored and not included in the public repo.

## Quick sanity check
Install dependencies and run the no-credential checks:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
scripts/sanity_check.sh
```

## Reproducibility
See:
- `ARTIFACT_MANIFEST.md`
- `ANONYMIZATION.md`
- `REPRODUCIBILITY.md`
- `runner/README.md`
- `REPO_MAP.md`

## Recent experimental artifacts

- Local structured-authorization protocols and reconstruction inputs:
  [frozen source protocols](scenarios/local-persistence-protocols/README.md).
- Four-checkpoint local outcome summaries:
  [unified experiment report](analysis/local_persistence_unified_20261011_v3.md)
  and [all assigned outcomes](analysis/local_persistence_unified_20261011_v3_summary.csv).
- [Native task-completion oracle](analysis/native_task_oracle_v1.md) and
  [model-extension protocol](analysis/native_extension_protocol_v1.md).
- [Confirmation amendment](analysis/confirmation_amendment_v1.md) and
  [external holdout amendment](analysis/external_holdout_amendment_v1.md).

Model observations, local proposal forks, and deterministic provider or
receipt conformance remain separate evidence units. Archived native task
presence and local exact-date full-task completion use different endpoints.
Frozen protocol inputs can be prepared without a model or API credential:

```bash
python3 analysis/prepare_local_persistence_protocols.py
```
