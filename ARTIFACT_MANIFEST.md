# PSEBench Artifact Manifest

This repository snapshot is prepared as a public benchmark artifact for
PSEBench. It contains the scenario corpus, runner code, analysis scripts,
summary tables, and reproducibility instructions needed to inspect and
regenerate the reported artifact-backed evidence.

Paper drafts, LaTeX sources, build outputs, local notes, machine-specific
configuration, and raw live-run directories are intentionally excluded from the
public snapshot.

## Artifact Scope

| Path | Public status | Purpose | Regeneration notes |
| --- | --- | --- | --- |
| `scenarios/` | included | Benchmark scenario YAMLs grouped by family and evaluation slice. | Static corpus; validated by `python3 analysis/schema_check.py`. |
| `data/web/` | included | Local benign, attack, and hybrid web fixtures referenced by web scenarios. | Static fixtures. |
| `runner/` | included | CLI, decision, proxy, policy, and local replication runners. | Main local no-notify entry point: `python3 runner/run_noncron_replication.py`. |
| `analysis/` | included | Aggregation, oracle, confidence-interval, and evidence-gap scripts plus exported summary tables. | Recompute derived summaries with the commands in `REPRODUCIBILITY.md`. |
| `oracles/` | included | Labeling/oracle conventions and helper materials. | Static documentation and helpers. |
| `tests/` | included | Unit checks for IACG intent/action-boundary behavior. | Run with `python3 -m unittest tests.test_intent_policy tests.test_hybrid_cli_policy`. |
| `results/STAGE_SUMMARY*.md` | included | Human-readable summaries of major experimental stages. | Static summaries of completed stages. |
| `results/runs/` | regenerated locally | Raw per-run artifacts such as `final.json`, `scenario.yaml`, `agent_output.txt`, and `cli_events.jsonl`. | Gitignored to avoid publishing local paths, transient logs, and machine-specific delivery metadata. |
| `runner/config.yaml` | local only | Machine-specific mappings, chat IDs, and optional honeypot paths. | Create from `runner/config.example.yaml` when needed. |
| `src/`, `build/`, `paper/`, `paper_writing/`, `presentation/` | excluded | Paper source, compiled PDFs, drafts, and presentation materials. | Not part of the public benchmark artifact. |

## Reproduction Tiers

### Tier 0: No-Credential Sanity Checks

These checks do not require live service credentials.

```bash
python3 -m unittest tests.test_intent_policy tests.test_hybrid_cli_policy
python3 analysis/schema_check.py
python3 -m py_compile runner/intent_policy.py runner/run_hybrid_cli.py runner/run_noncron_replication.py analysis/auto_oracle_noncron.py analysis/evidence_gap_tables.py
```

### Tier 1: Local Non-Cron Replication

This tier regenerates the final `riskfix2-*` file, calendar, recipient, and
legitimate-persistence artifacts without live notification delivery.

```bash
python3 runner/run_noncron_replication.py
python3 analysis/auto_oracle_noncron.py
python3 analysis/evidence_gap_tables.py
```

Expected high-level outputs:

| Output | Expected property |
| --- | --- |
| `analysis/noncron_replication_summary.csv` | file/calendar/recipient permissive attacks succeed, while IACG blocks unauthorized persistent or broader-scope actions and preserves legitimate file/calendar persistence. |
| `analysis/auto_oracle_noncron_summary.csv` | artifact oracle agrees with stored labels for supported non-cron artifact-backed runs. |
| `analysis/artifact_oracle_coverage_summary.csv` | combines cron and non-cron artifact-oracle coverage. |

The generated raw directories under `results/runs/riskfix2-*` remain local by
default. They can be deleted and regenerated from the commands above.

### Tier 2: Derived Summary Regeneration

After representative raw artifacts exist locally, regenerate derived tables:

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
```

### Tier 3: Live or Model-Driven Replication

Live message-delivery and model-driven slices may require local credentials,
agent binaries, and delivery targets. They are documented in
`REPRODUCIBILITY.md` and `runner/README.md`, but they are not required for the
no-credential artifact sanity check.

## Evidence Boundary

PSEBench reports IACG as a conservative, rule-based action-boundary/reference
monitor. It is not claimed to be a general semantic reasoner or a complete
prompt-injection defense. Scenario `intent` and `oracle` fields are labeling and
aggregation metadata; they are not hidden runtime inputs to IACG.

The raw live-run directories are not committed because they can contain local
paths, transient logs, and delivery metadata. Public CSV/Markdown summaries and
the no-notify replication scripts provide the artifact-facing reproduction path.
