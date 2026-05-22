# PSEBench Reproducibility Notes

This document records the minimal repeatable steps for reproducing representative benchmark runs and summary tables.

## 1) Environment
- OS: macOS (tested)
- Python: 3.14+
- OpenClaw CLI: 2026.3.1+

## 2) Install
```bash
cd ~/Desktop/PSEBench
python3 -m venv .venv
source .venv/bin/activate
pip install -U pyyaml
```

Optional local config:
```bash
cp runner/config.example.yaml runner/config.yaml
```

`runner/config.yaml` is intentionally machine-local and gitignored.

## 3) Main runner modes
### CLI runner (hybrid)
Permissive:
```bash
python3 runner/run_hybrid_cli.py scenarios/hybrid/H-msg-cron-required-002.yaml \
  --run-id demo --tag permissive --chat-id <CHAT_ID> --allow-injected
```

IACG:
```bash
python3 runner/run_hybrid_cli.py scenarios/hybrid/H-msg-cron-required-002.yaml \
  --run-id demo --tag iacg --chat-id <CHAT_ID>
```

Firewall:
```bash
python3 runner/run_hybrid_cli.py scenarios/hybrid/H-msg-cron-required-002.yaml \
  --run-id demo --tag firewall --chat-id <CHAT_ID> --firewall
```

Confirm-all-persistent:
```bash
python3 runner/run_hybrid_cli.py scenarios/hybrid/H-msg-cron-required-002.yaml \
  --run-id demo --tag confirm-all-persistent --chat-id <CHAT_ID> --confirm-all-persistent
```

SLC:
```bash
python3 runner/run_hybrid_cli.py scenarios/hybrid-failure-cron/H-msg-cron-required-FAIL-001.yaml \
  --run-id demo --tag slc --chat-id <CHAT_ID> --allow-injected --slc
```

### Decision runner (model-driven)
```bash
python3 runner/run_hybrid_decision.py scenarios/hybrid/H-msg-cron-required-002.yaml \
  --run-id live5 --tag live5-permissive --chat-id <CHAT_ID> \
  --decision-policy permissive --agent replica
```

```bash
python3 runner/run_hybrid_decision.py scenarios/hybrid/H-msg-cron-required-002.yaml \
  --run-id live5 --tag live5-guard --chat-id <CHAT_ID> \
  --decision-policy permissive --agent replica --guard
```

## 4) Important scenario slices
- core cron matched slice: `scenarios/hybrid/`
- authorization-boundary contrast: `scenarios/hybrid-contrast-cron/`
- implicit durability: `scenarios/hybrid-implicit-cron/`
- failure stress set: `scenarios/hybrid-failure-cron/`
- file persistence: `scenarios/hybrid-file/`
- calendar recurrence: `scenarios/hybrid-calendar/`
- recipient hijack: `scenarios/hybrid-msg/`

## 5) Run artifacts
Each run creates a directory under:
- `results/runs/<run-id>-<tag>/<scenario_id>/`

Common artifacts include:
- `final.json`
- `scenario.yaml`
- `agent_output.txt`
- `cli_events.jsonl` for CLI runs
- `decision.json` for decision/model-driven runs when present

## 6) Aggregate tables
```bash
python3 analysis/auto_oracle_from_cli.py
python3 analysis/auto_oracle_agreement.py
python3 analysis/auto_oracle_noncron.py
python3 analysis/compute_ci_tables.py
python3 analysis/confirm_all_persistent_report.py
python3 analysis/slc_report.py
python3 analysis/reviewer_gap_tables.py
python3 analysis/benchmark_guard_overhead.py
```

Representative outputs:
- `analysis/main_table_by_run.csv`
- `analysis/main_table_by_family.csv`
- `analysis/main_table_by_group.csv`
- `analysis/confirm_all_persistent_summary.csv`
- `analysis/slc_summary.csv`
- `analysis/new_baseline_comparison_table.csv`
- `analysis/prompt_only_baseline_summary.csv`
- `analysis/oracle_coverage_summary.csv`
- `analysis/auto_oracle_agreement_summary.csv`
- `analysis/auto_oracle_noncron_summary.csv`
- `analysis/iacg_overhead_summary.csv`

## 7) Guard schema in `final.json`
Representative fields:
```json
"guard": {
  "guard_policy": "iapg",
  "intent": "one-shot",
  "intent_evidence": ["once"],
  "action_kind": "recurring",
  "guard_decision": "block",
  "guard_reason": "intent one-shot conflicts with recurring action"
}
```
