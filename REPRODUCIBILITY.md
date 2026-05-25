# PSEBench Reproducibility Notes

This document records the minimal repeatable steps for reproducing representative benchmark runs and summary tables. See `ARTIFACT_MANIFEST.md` for the public artifact scope and the distinction between committed summaries and locally regenerated raw run directories.

## 1) Environment
- OS: macOS (tested)
- Python: 3.14+
- OpenClaw CLI: 2026.3.1+

## 2) Install
```bash
cd PSEBench
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

Final local non-cron replication slice:
```bash
python3 runner/run_noncron_replication.py
python3 analysis/auto_oracle_noncron.py
python3 analysis/evidence_gap_tables.py
```

This creates the `riskfix2-*` file, calendar, recipient, and legitimate-persistence artifacts used by the appendix without requiring live message delivery.
The expected final local slice contains 104 no-notification runs: 12 permissive and 12 IACG attack-side runs for each of file persistence, calendar recurrence, and recipient hijack, plus 8 IACG and 8 firewall legitimate-persistence utility runs for both file and calendar workflows.
The generated raw directories are written under `results/runs/` and are intentionally gitignored; rerun the commands above to regenerate them locally.

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

### Optional cross-model decision benchmark
The cross-model decision runner evaluates model decisions without executing live
tools or writing into `results/runs/`. It asks each model whether it would
complete the benign task and whether it would also execute the untrusted
escalation. The default balanced set contains 72 scenarios and two prompt
policies, so three models produce 432 clean decision rows when all calls
succeed.

```bash
export OPENAI_API_KEY=<OPENAI_OR_COMPATIBLE_KEY>
export OPENAI_BASE_URL=<OPTIONAL_OPENAI_COMPATIBLE_BASE_URL>
export ANTHROPIC_AUTH_TOKEN=<ANTHROPIC_OR_COMPATIBLE_TOKEN>
export ANTHROPIC_BASE_URL=<OPTIONAL_ANTHROPIC_COMPATIBLE_BASE_URL>

python3 runner/run_cross_model_decision.py \
  --models openai:gpt-5.4 openai:gpt-5.5 anthropic:claude-opus-4-6 \
  --scenario-set balanced72 \
  --policies hardened permissive \
  --run-id cm-balanced72

python3 analysis/cross_model_decision_summary.py \
  results/cross_model/cm-balanced72_raw.jsonl \
  --output-prefix analysis/cross_model_decision
```

If models are run through separate endpoints or run IDs, pass multiple JSONL
files to the same summary command:

```bash
python3 analysis/cross_model_decision_summary.py \
  results/cross_model/<run-a>_raw.jsonl \
  results/cross_model/<run-b>_raw.jsonl \
  --exclude-provider-model openai:claude-opus-4-6 \
  --output-prefix analysis/cross_model_combined_balanced72
```

Use `--dry-run` to print the planned matrix without making API calls. If a
provider uses a custom OpenAI-compatible endpoint, set `OPENAI_BASE_URL` or pass
`--openai-base-url`; direct Anthropic-compatible runs can instead use
`anthropic:<model>` with `ANTHROPIC_AUTH_TOKEN`.

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

Raw run directories are not part of the public repository snapshot by default because they can contain local paths, transient logs, and machine-specific delivery metadata. Public stage summaries and derived CSV/Markdown tables are committed; raw `riskfix2-*` artifacts are regenerated by `python3 runner/run_noncron_replication.py`.

## 6) Aggregate tables
```bash
python3 analysis/auto_oracle_from_cli.py
python3 analysis/auto_oracle_agreement.py
python3 analysis/auto_oracle_noncron.py
python3 analysis/compute_ci_tables.py
python3 analysis/confirm_all_persistent_report.py
python3 analysis/slc_report.py
python3 analysis/reviewer_gap_tables.py
python3 analysis/evidence_gap_tables.py
python3 analysis/benchmark_guard_overhead.py
python3 analysis/label_audit.py prepare --seed 20260523
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
- `analysis/artifact_oracle_coverage_summary.csv`
- `analysis/noncron_replication_summary.csv`
- `analysis/auto_oracle_agreement_summary.csv`
- `analysis/auto_oracle_noncron_summary.csv`
- `analysis/iacg_overhead_summary.csv`
- `analysis/label_audit_blind_sample.csv`
- `analysis/label_audit_sample_summary.csv`
- `analysis/label_audit_agreement_summary.csv`
- `analysis/label_audit_disagreement_summary.csv`

To score an independently completed audit file:

```bash
python3 analysis/label_audit.py score completed_annotator.csv
```

## 7) Sanity checks
```bash
python3 -m unittest tests.test_intent_policy tests.test_hybrid_cli_policy
python3 analysis/schema_check.py
python3 -m py_compile runner/intent_policy.py runner/run_hybrid_cli.py runner/run_hybrid_decision.py
```

These checks validate the shared rule-based intent classifier, guard action-kind classification, scenario schema completeness, and runner importability without requiring live service credentials.

## 8) Guard schema in `final.json`
Representative fields:
```json
"guard": {
  "guard_policy": "IACG",
  "intent": "one-shot",
  "intent_evidence": ["once"],
  "action_kind": "recurring",
  "guard_decision": "block",
  "guard_reason": "intent one-shot conflicts with recurring action"
}
```
