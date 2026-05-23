# Runner

This directory contains the executable benchmark harnesses.

## Main entry points
- `run_hybrid_cli.py` — CLI-backed runner for hybrid scenarios; currently the main benchmark runner.
- `run_hybrid_decision.py` — model-driven / decision runner.
- `run_hybrid_decision_proxy.py` — proxy-based decision runner.
- `run_noncron_replication.py` — local reproduction script for the final `riskfix2-*` non-cron replication slice.
- `run.py` — older/general entry point.

## Common outputs
Runs are written under:
- `results/runs/<run-id>-<tag>/<scenario_id>/`

Common artifacts include:
- `final.json`
- `scenario.yaml`
- `agent_output.txt`
- `cli_events.jsonl` (CLI-backed runs)
- `decision.json` (decision/model-driven runs, when present)

## Current baseline switches in `run_hybrid_cli.py`
- permissive: `--allow-injected`
- firewall: `--firewall`
- confirm-all-persistent: `--confirm-all-persistent`
- SLC: `--slc`
- IACG: default guarded comparison path (no permissive/firewall/SLC/confirm-all-persistent override)

## Local config
If you need machine-specific target mappings or honeypot paths, copy the example file:

```bash
cp runner/config.example.yaml runner/config.yaml
```

`runner/config.yaml` is gitignored and stays local.

## Notes
- The CLI runner is currently the canonical path for the persistence-escalation baselines.
