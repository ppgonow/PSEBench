#!/usr/bin/env bash
set -euo pipefail

python3 -m unittest tests.test_intent_policy tests.test_hybrid_cli_policy
python3 analysis/schema_check.py
python3 -m py_compile \
  runner/intent_policy.py \
  runner/run_hybrid_cli.py \
  runner/run_noncron_replication.py \
  runner/run_cross_model_decision.py \
  analysis/auto_oracle_noncron.py \
  analysis/evidence_gap_tables.py \
  analysis/label_audit.py \
  analysis/cross_model_decision_summary.py \
  analysis/paper_figures_and_tables.py
