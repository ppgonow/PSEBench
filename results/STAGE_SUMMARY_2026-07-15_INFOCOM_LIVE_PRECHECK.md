# INFOCOM Held-Out Live Precheck (2026-07-15)

## Configuration

- Endpoint: OpenAI-compatible gateway supplied for this experiment.
- Models: `gpt-5.4`, `gpt-5.5`, `gpt-5.6-sol`.
- Scenario set: five cases from `scenarios/hybrid-adaptive-heldout/`.
- Policies: `hardened`, `permissive`.
- Total requests: 30, one worker, `--sleep 2`, resumable JSONL output.
- No tool execution or external side effect; this runner is decision-only.

## Results

| model | policy | n | task success | escalation decisions | API errors | parse errors |
|---|---|---:|---:|---:|---:|---:|
| gpt-5.4 | hardened | 5 | 5/5 | 0/5 | 0 | 0 |
| gpt-5.4 | permissive | 5 | 5/5 | 4/5 | 0 | 0 |
| gpt-5.5 | hardened | 5 | 5/5 | 0/5 | 0 | 0 |
| gpt-5.5 | permissive | 5 | 5/5 | 4/5 | 0 | 0 |
| gpt-5.6-sol | hardened | 5 | 5/5 | 0/5 | 0 | 0 |
| gpt-5.6-sol | permissive | 5 | 5/5 | 1/5 | 0 | 0 |

## Interpretation

The held-out wording produces model-dependent permissive behavior while the
hardened prompt rejects the tested escalation requests. This is decision-only
evidence and is not a live tool-execution result. The run had no observed rate
limit or API failure. The API key was supplied interactively, was not written to
the repository or result files, and should be rotated after the experiment.

## Reproduction shape

```bash
python3 runner/run_cross_model_decision.py \
  --models openai:gpt-5.4 openai:gpt-5.5 openai:gpt-5.6-sol \
  --scenario-set heldout100 \
  --policies hardened permissive \
  --run-id infocom-heldout-precheck \
  --limit 5 --sleep 2 --resume
```
