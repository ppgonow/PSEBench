# Oracles

This directory contains oracle notes and helper scripts for labeling benchmark outcomes from run artifacts.

## Current role
The repository currently uses a mix of:
- rule-based labeling from CLI/tool artifacts
- manual labels stored in `final.json`
- aggregation scripts in `analysis/`

## Important files
- `label_manual.py` — manual labeling helper
- `label_audit_protocol.md` — blinded second-annotator audit instructions
- `oracles.md` — oracle notes / conventions

## Related analysis scripts
Most run-level aggregation currently happens in `analysis/`, especially:
- `analysis/auto_oracle_from_cli.py`
- `analysis/label_audit.py`
- `analysis/compute_ci_tables.py`

## Conceptual oracle types
- ExecOracle — command execution
- MessageOracle — exfiltration / recipient misuse
- CronOracle — persistence / recurrence creation
- NodesOracle — camera / screen / location actions
- FileOracle — honeypot file access / persistence state
