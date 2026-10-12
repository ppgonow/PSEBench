#!/usr/bin/env bash
set -euo pipefail

python3 -m unittest discover -s tests -p 'test_*.py'
python3 analysis/schema_check.py
python3 analysis/audit_receipt_field_ablation.py \
  --detail analysis/receipt_field_ablation_detail.csv \
  --output-prefix tmp/sanity_receipt_field_ablation
cmp analysis/receipt_field_ablation_summary.csv tmp/sanity_receipt_field_ablation_summary.csv
cmp analysis/receipt_field_ablation_paired.csv tmp/sanity_receipt_field_ablation_paired.csv
cmp analysis/receipt_field_ablation_integrity.csv tmp/sanity_receipt_field_ablation_integrity.csv
python3 runner/run_receipt_mask_ablation.py \
  --detail tmp/sanity_receipt_mask_ablation_detail.csv \
  --integrity tmp/sanity_receipt_mask_ablation_integrity.json \
  --overwrite
python3 analysis/audit_receipt_mask_ablation.py \
  --detail tmp/sanity_receipt_mask_ablation_detail.csv \
  --output-prefix tmp/sanity_receipt_mask_ablation
cmp analysis/receipt_mask_ablation_summary.csv \
  tmp/sanity_receipt_mask_ablation_summary.csv
cmp analysis/receipt_mask_ablation_family.csv \
  tmp/sanity_receipt_mask_ablation_family.csv
cmp analysis/receipt_mask_ablation_integrity.json \
  tmp/sanity_receipt_mask_ablation_integrity.json
python3 analysis/audit_same_tool_normalization.py \
  --output-prefix tmp/sanity_same_tool_normalization \
  --overwrite
cmp analysis/same_tool_normalization_detail.csv tmp/sanity_same_tool_normalization_detail.csv
cmp analysis/same_tool_normalization_summary.csv tmp/sanity_same_tool_normalization_summary.csv
cmp analysis/same_tool_normalization_integrity.csv tmp/sanity_same_tool_normalization_integrity.csv
python3 analysis/summarize_same_tool_native_commit.py \
  --final \
    analysis/same_tool_native_commit_gpt_5_5_final.jsonl \
    analysis/same_tool_native_commit_grok_4_5_final.jsonl \
    analysis/same_tool_native_commit_gpt_5_4_final.jsonl \
    analysis/same_tool_native_commit_gpt_5_6_sol_final.jsonl \
  --output-prefix tmp/sanity_same_tool_native_commit
cmp analysis/same_tool_native_commit_detail.csv tmp/sanity_same_tool_native_commit_detail.csv
cmp analysis/same_tool_native_commit_summary.csv tmp/sanity_same_tool_native_commit_summary.csv
cmp analysis/same_tool_native_commit_paired.csv tmp/sanity_same_tool_native_commit_paired.csv
cmp analysis/same_tool_native_commit_exposure_paired.csv tmp/sanity_same_tool_native_commit_exposure_paired.csv
cmp analysis/same_tool_native_commit_cluster_paired.csv tmp/sanity_same_tool_native_commit_cluster_paired.csv
cmp analysis/same_tool_native_commit_cluster_bootstrap.csv tmp/sanity_same_tool_native_commit_cluster_bootstrap.csv
cmp analysis/same_tool_native_commit_multiplicity.csv tmp/sanity_same_tool_native_commit_multiplicity.csv
cmp analysis/same_tool_native_commit_precision.csv tmp/sanity_same_tool_native_commit_precision.csv
cmp analysis/same_tool_native_commit_commit_detail.csv tmp/sanity_same_tool_native_commit_commit_detail.csv
cmp analysis/same_tool_native_commit_commit_summary.csv tmp/sanity_same_tool_native_commit_commit_summary.csv
cmp analysis/same_tool_native_commit_integrity.csv tmp/sanity_same_tool_native_commit_integrity.csv
if [[ -f results/native_service_commit_bridge/native_service_commit_bridge.jsonl \
   && -f results/native_service_commit_bridge/native_service_commit_bridge_attempts.jsonl ]]; then
  python3 analysis/audit_native_service_commit_bridge.py \
    --output tmp/sanity_native_service_commit_bridge_audit.csv
  cmp analysis/native_service_commit_bridge_audit.csv tmp/sanity_native_service_commit_bridge_audit.csv
else
  echo "Skipping native service bridge raw-run audit: raw JSONL is local-only." >&2
fi
python3 analysis/audit_adaptive_effect_v2.py \
  --output-prefix tmp/sanity_adaptive_effect_v2
cmp analysis/adaptive_effect_v2_detail.csv tmp/sanity_adaptive_effect_v2_detail.csv
cmp analysis/adaptive_effect_v2_summary.csv tmp/sanity_adaptive_effect_v2_summary.csv
cmp analysis/adaptive_effect_v2_integrity.csv tmp/sanity_adaptive_effect_v2_integrity.csv
python3 analysis/audit_adapter_observer_holdout.py \
  --output-prefix tmp/sanity_adapter_observer_holdout \
  --overwrite
cmp analysis/adapter_observer_holdout_detail.csv \
  tmp/sanity_adapter_observer_holdout_detail.csv
cmp analysis/adapter_observer_holdout_summary.csv \
  tmp/sanity_adapter_observer_holdout_summary.csv
cmp analysis/adapter_observer_holdout_coverage.csv \
  tmp/sanity_adapter_observer_holdout_coverage.csv
cmp analysis/adapter_observer_holdout_integrity.csv \
  tmp/sanity_adapter_observer_holdout_integrity.csv
posix_expected_prefix="analysis/posix_file_provider"
if [[ "$(uname -s)" == "Linux" ]]; then
  posix_expected_prefix="analysis/posix_file_provider_linux"
fi
python3 analysis/audit_posix_file_provider.py \
  --output-prefix tmp/sanity_posix_file_provider \
  --overwrite
cmp "${posix_expected_prefix}_detail.csv" \
  tmp/sanity_posix_file_provider_detail.csv
cmp "${posix_expected_prefix}_summary.csv" \
  tmp/sanity_posix_file_provider_summary.csv
cmp "${posix_expected_prefix}_effect_detail.csv" \
  tmp/sanity_posix_file_provider_effect_detail.csv
cmp "${posix_expected_prefix}_integrity.csv" \
  tmp/sanity_posix_file_provider_integrity.csv
if [[ -d tmp/radicale_runtime ]]; then
  python3 analysis/audit_caldav_provider.py \
    --output-prefix tmp/sanity_caldav_provider \
    --overwrite
  cmp analysis/caldav_provider_detail.csv tmp/sanity_caldav_provider_detail.csv
  cmp analysis/caldav_provider_summary.csv tmp/sanity_caldav_provider_summary.csv
  cmp analysis/caldav_provider_integrity.json tmp/sanity_caldav_provider_integrity.json
else
  echo "Skipping optional CalDAV provider audit: install requirements-provider.txt to enable it." >&2
fi
if [[ -f analysis/same_tool_native_commit_grok_4_6_final.jsonl ]]; then
  python3 analysis/audit_native_extension.py \
    analysis/same_tool_native_commit_grok_4_6_final.jsonl \
    --alias grok-4.6 \
    --output tmp/sanity_native_extension_grok_4_6_integrity.json
  cmp analysis/native_extension_grok_4_6_integrity.json \
    tmp/sanity_native_extension_grok_4_6_integrity.json
fi
python3 formal/bounded_security_model.py >/dev/null
python3 formal/bounded_oracle_lattice.py >/dev/null
python3 formal/bounded_multi_principal_authority.py \
  --output tmp/sanity_multi_principal_authority.json >/dev/null
cmp analysis/multi_principal_authority_summary.json \
  tmp/sanity_multi_principal_authority.json
python3 analysis/audit_feedback_adaptive_v2.py \
  --output-prefix tmp/sanity_feedback_adaptive_v2
cmp analysis/feedback_adaptive_v2_detail.csv \
  tmp/sanity_feedback_adaptive_v2_detail.csv
cmp analysis/feedback_adaptive_v2_summary.csv \
  tmp/sanity_feedback_adaptive_v2_summary.csv
if [[ -d external/official_reproduction/agentdojo \
   && -d external/official_reproduction/agentdojo-core ]]; then
  python3 analysis/audit_benchmark_oracle_capabilities.py \
    --output-prefix tmp/sanity_benchmark_oracle_capability
  cmp analysis/benchmark_oracle_capability_audit.csv tmp/sanity_benchmark_oracle_capability_audit.csv
  cmp analysis/benchmark_oracle_capability_task_inventory.csv tmp/sanity_benchmark_oracle_capability_task_inventory.csv
  cmp analysis/benchmark_oracle_capability_integrity.csv tmp/sanity_benchmark_oracle_capability_integrity.csv

  oracle_python=""
  for candidate in python3 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11; do
    if command -v "$candidate" >/dev/null 2>&1 \
       && "$candidate" -c "import pydantic; assert hasattr(pydantic.BaseModel, 'model_copy')" >/dev/null 2>&1; then
      oracle_python="$candidate"
      break
    fi
  done
  if [[ -n "$oracle_python" ]]; then
    "$oracle_python" analysis/audit_official_oracle_distinguishability.py \
      --output-prefix tmp/sanity_official_oracle_distinguishability
    cmp analysis/official_oracle_distinguishability_detail.csv tmp/sanity_official_oracle_distinguishability_detail.csv
    cmp analysis/official_oracle_distinguishability_summary.csv tmp/sanity_official_oracle_distinguishability_summary.csv
    cmp analysis/official_oracle_distinguishability_integrity.csv tmp/sanity_official_oracle_distinguishability_integrity.csv
  else
    echo "Skipping official oracle distinguishability regeneration: Pydantic 2 is unavailable." >&2
  fi
fi
python3 analysis/independent_unit_analysis.py
python3 analysis/summarize_native_e2e.py \
  analysis/native_e2e48_final.jsonl \
  --output-prefix tmp/sanity_native_e2e48
cmp analysis/native_e2e48_detail.csv tmp/sanity_native_e2e48_detail.csv
cmp analysis/native_e2e48_summary.csv tmp/sanity_native_e2e48_summary.csv
cmp analysis/native_e2e48_paired.csv tmp/sanity_native_e2e48_paired.csv
cmp analysis/native_e2e48_final.jsonl tmp/sanity_native_e2e48_final.jsonl
python3 analysis/summarize_adaptive_native_fork.py \
  analysis/adaptive_native_fork_holdout_final.jsonl \
  --manifest scenarios/adaptive-native-holdout/MANIFEST.csv \
  --models gpt-5.5 grok-4.5 \
  --output-prefix tmp/sanity_adaptive_native
cmp analysis/adaptive_native_fork_holdout_summary.csv tmp/sanity_adaptive_native_summary.csv
cmp analysis/adaptive_native_fork_holdout_paired.csv tmp/sanity_adaptive_native_paired.csv
python3 analysis/audit_adaptive_native_fork.py \
  --raw analysis/adaptive_native_fork_holdout_final.jsonl \
  --final analysis/adaptive_native_fork_holdout_final.jsonl \
  --ledger-csv analysis/adaptive_native_fork_holdout_postrun_audit_ledger.csv \
  --output-prefix tmp/sanity_adaptive_native_audit
cmp analysis/adaptive_native_fork_holdout_postrun_audit_detail.csv tmp/sanity_adaptive_native_audit_detail.csv
cmp analysis/adaptive_native_fork_holdout_postrun_audit_by_boundary.csv tmp/sanity_adaptive_native_audit_by_boundary.csv
cmp analysis/adaptive_native_fork_holdout_postrun_audit_paired.csv tmp/sanity_adaptive_native_audit_paired.csv
cmp analysis/adaptive_native_fork_holdout_postrun_audit_metadata.csv tmp/sanity_adaptive_native_audit_metadata.csv
python3 analysis/summarize_adaptive_native_fork.py \
  analysis/adaptive_native_fork_schema_neutral_final.jsonl \
  --manifest scenarios/adaptive-native-holdout/MANIFEST.csv \
  --models gpt-5.5 grok-4.5 \
  --output-prefix tmp/sanity_adaptive_native_schema_neutral
cmp analysis/adaptive_native_fork_schema_neutral_summary.csv tmp/sanity_adaptive_native_schema_neutral_summary.csv
cmp analysis/adaptive_native_fork_schema_neutral_paired.csv tmp/sanity_adaptive_native_schema_neutral_paired.csv
python3 analysis/audit_adaptive_native_fork.py \
  --raw analysis/adaptive_native_fork_schema_neutral_final.jsonl \
  --final analysis/adaptive_native_fork_schema_neutral_final.jsonl \
  --ledger-csv analysis/adaptive_native_fork_schema_neutral_postrun_audit_ledger.csv \
  --output-prefix tmp/sanity_adaptive_native_schema_neutral_audit
cmp analysis/adaptive_native_fork_schema_neutral_postrun_audit_detail.csv tmp/sanity_adaptive_native_schema_neutral_audit_detail.csv
cmp analysis/adaptive_native_fork_schema_neutral_postrun_audit_by_boundary.csv tmp/sanity_adaptive_native_schema_neutral_audit_by_boundary.csv
cmp analysis/adaptive_native_fork_schema_neutral_postrun_audit_paired.csv tmp/sanity_adaptive_native_schema_neutral_audit_paired.csv
cmp analysis/adaptive_native_fork_schema_neutral_postrun_audit_metadata.csv tmp/sanity_adaptive_native_schema_neutral_audit_metadata.csv
python3 analysis/summarize_adaptive_native_fork.py \
  analysis/adaptive_native_fork_gpt54_gpt56_final.jsonl \
  --manifest scenarios/adaptive-native-holdout/MANIFEST.csv \
  --models gpt-5.4 gpt-5.6-sol \
  --output-prefix tmp/sanity_adaptive_native_gpt54_gpt56
cmp analysis/adaptive_native_fork_gpt54_gpt56_summary.csv tmp/sanity_adaptive_native_gpt54_gpt56_summary.csv
cmp analysis/adaptive_native_fork_gpt54_gpt56_paired.csv tmp/sanity_adaptive_native_gpt54_gpt56_paired.csv
cmp analysis/adaptive_native_fork_gpt54_gpt56_final.jsonl tmp/sanity_adaptive_native_gpt54_gpt56_final.jsonl
python3 analysis/audit_adaptive_native_fork.py \
  --raw analysis/adaptive_native_fork_gpt54_gpt56_final.jsonl \
  --final analysis/adaptive_native_fork_gpt54_gpt56_final.jsonl \
  --ledger-csv analysis/adaptive_native_fork_gpt54_gpt56_postrun_audit_ledger.csv \
  --output-prefix tmp/sanity_adaptive_native_gpt54_gpt56_audit \
  --allow-terminal-without-effect
cmp analysis/adaptive_native_fork_gpt54_gpt56_postrun_audit_detail.csv tmp/sanity_adaptive_native_gpt54_gpt56_audit_detail.csv
cmp analysis/adaptive_native_fork_gpt54_gpt56_postrun_audit_by_boundary.csv tmp/sanity_adaptive_native_gpt54_gpt56_audit_by_boundary.csv
cmp analysis/adaptive_native_fork_gpt54_gpt56_postrun_audit_paired.csv tmp/sanity_adaptive_native_gpt54_gpt56_audit_paired.csv
cmp analysis/adaptive_native_fork_gpt54_gpt56_postrun_audit_metadata.csv tmp/sanity_adaptive_native_gpt54_gpt56_audit_metadata.csv
cmp analysis/adaptive_native_fork_gpt54_gpt56_postrun_audit_integrity.csv tmp/sanity_adaptive_native_gpt54_gpt56_audit_integrity.csv
python3 analysis/analyze_adaptive_native_templates.py \
  --manifest scenarios/adaptive-native-holdout/MANIFEST.csv \
  --final \
    analysis/adaptive_native_fork_schema_neutral_final.jsonl \
    analysis/adaptive_native_fork_gpt54_gpt56_final.jsonl \
  --output-prefix tmp/sanity_adaptive_native_templates
cmp analysis/adaptive_native_templates_detail.csv tmp/sanity_adaptive_native_templates_detail.csv
cmp analysis/adaptive_native_templates_summary.csv tmp/sanity_adaptive_native_templates_summary.csv
python3 analysis/run_method_comparison.py \
  --output-dir tmp/sanity_method_comparison \
  --output-label candidate_action
cmp analysis/method_comparison_detail_candidate_action.csv tmp/sanity_method_comparison/method_comparison_detail_candidate_action.csv
cmp analysis/method_comparison_overall_candidate_action.csv tmp/sanity_method_comparison/method_comparison_overall_candidate_action.csv
cmp analysis/method_comparison_by_slice_candidate_action.csv tmp/sanity_method_comparison/method_comparison_by_slice_candidate_action.csv
cmp analysis/method_comparison_overall_candidate_action.md tmp/sanity_method_comparison/method_comparison_overall_candidate_action.md
python3 analysis/audit_multiprocess_commit_race.py \
  --detail analysis/multiprocess_commit_race_detail.csv \
  --output-prefix tmp/sanity_multiprocess_commit_race
cmp analysis/multiprocess_commit_race_summary.csv tmp/sanity_multiprocess_commit_race_summary.csv
cmp analysis/multiprocess_commit_race_paired.csv tmp/sanity_multiprocess_commit_race_paired.csv
cmp analysis/multiprocess_commit_race_audit_integrity.csv tmp/sanity_multiprocess_commit_race_integrity.csv
python3 analysis/audit_commit_gateway_load.py \
  --detail analysis/commit_gateway_load_detail.csv \
  --output tmp/sanity_commit_gateway_load_summary.csv
cmp analysis/commit_gateway_load_summary.csv tmp/sanity_commit_gateway_load_summary.csv
python3 analysis/audit_network_schedule.py \
  --detail analysis/network_schedule_detail.csv \
  --output tmp/sanity_network_schedule_summary.csv
cmp analysis/network_schedule_summary.csv tmp/sanity_network_schedule_summary.csv
python3 analysis/analyze_network_schedule_results.py \
  --detail analysis/network_schedule_detail.csv \
  --output-prefix tmp/sanity_network_schedule
cmp analysis/network_schedule_inference.csv tmp/sanity_network_schedule_inference.csv
cmp analysis/network_schedule_by_family.csv tmp/sanity_network_schedule_by_family.csv
cmp analysis/network_schedule_paired.csv tmp/sanity_network_schedule_paired.csv
python3 analysis/audit_async_queue_commit.py \
  --detail analysis/async_queue_commit_detail.csv \
  --output-prefix tmp/sanity_async_queue_commit
cmp analysis/async_queue_commit_summary.csv tmp/sanity_async_queue_commit_summary.csv
cmp analysis/async_queue_commit_integrity.csv tmp/sanity_async_queue_commit_integrity.csv
python3 analysis/audit_docker_queue_failover.py \
  --detail analysis/docker_queue_failover_detail.csv \
  --metadata analysis/docker_queue_failover_metadata.csv \
  --output-prefix tmp/sanity_docker_queue_failover
cmp analysis/docker_queue_failover_summary.csv tmp/sanity_docker_queue_failover_summary.csv
cmp analysis/docker_queue_failover_integrity.csv tmp/sanity_docker_queue_failover_integrity.csv
python3 analysis/audit_service_integrated_commit.py \
  --detail analysis/service_integrated_commit_detail.csv \
  --output-prefix tmp/sanity_service_integrated_commit
cmp analysis/service_integrated_commit_summary.csv tmp/sanity_service_integrated_commit_summary.csv
cmp analysis/service_integrated_commit_integrity.csv tmp/sanity_service_integrated_commit_integrity.csv
python3 analysis/audit_postgres_integrated_commit.py \
  --detail analysis/postgres_integrated_commit_detail.csv \
  --metadata analysis/postgres_integrated_commit_metadata.csv \
  --output-prefix tmp/sanity_postgres_integrated_commit
cmp analysis/postgres_integrated_commit_summary.csv tmp/sanity_postgres_integrated_commit_summary.csv
cmp analysis/postgres_integrated_commit_integrity.csv tmp/sanity_postgres_integrated_commit_integrity.csv
python3 analysis/audit_container_commit_race.py \
  --detail analysis/container_commit_race_detail.csv \
  --topology analysis/container_commit_race_topology.csv \
  --output-prefix tmp/sanity_container_commit_race
cmp analysis/container_commit_race_summary.csv tmp/sanity_container_commit_race_summary.csv
cmp analysis/container_commit_race_paired.csv tmp/sanity_container_commit_race_paired.csv
cmp analysis/container_commit_race_audit_integrity.csv tmp/sanity_container_commit_race_integrity.csv
python3 analysis/audit_multihost_commit_race.py \
  --detail analysis/multihost_commit_race_detail.csv \
  --topology analysis/multihost_commit_race_topology.csv \
  --output-prefix tmp/sanity_multihost_commit_race
cmp analysis/multihost_commit_race_summary.csv tmp/sanity_multihost_commit_race_summary.csv
cmp analysis/multihost_commit_race_paired.csv tmp/sanity_multihost_commit_race_paired.csv
cmp analysis/multihost_commit_race_audit_integrity.csv tmp/sanity_multihost_commit_race_integrity.csv
env PYTHONPYCACHEPREFIX=tmp/pycache python3 -m compileall -q runner analysis
