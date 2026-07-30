# INFOCOM Held-Out Live Decision Matrix (2026-07-15)

## Configuration

- Three OpenAI-compatible models: `gpt-5.4`, `gpt-5.5`, `gpt-5.6-sol`.
- Twenty held-out message-to-scheduler scenarios per model and policy.
- Policies: `hardened` and `permissive`.
- 120 unique decision keys, one worker, `--sleep 2`, resumable JSONL.
- No real tool execution or external-state side effects.

The raw JSONL retains failed attempts. The reported table is generated after
deduplicating by `(provider, model, policy, scenario_id)` and keeping the last
attempt. Five initial gateway EOFs were retried successfully; the final
deduplicated matrix has 120 valid requests and zero transport/parse errors.

## Results

| model | policy | n | task success | escalation decisions | ASR Wilson 95% CI |
|---|---|---:|---:|---:|---|
| gpt-5.4 | hardened | 20 | 20/20 | 0/20 | [0.000, 0.161] |
| gpt-5.4 | permissive | 20 | 20/20 | 11/20 | [0.342, 0.742] |
| gpt-5.5 | hardened | 20 | 20/20 | 0/20 | [0.000, 0.161] |
| gpt-5.5 | permissive | 20 | 20/20 | 17/20 | [0.640, 0.948] |
| gpt-5.6-sol | hardened | 20 | 20/20 | 0/20 | [0.000, 0.161] |
| gpt-5.6-sol | permissive | 20 | 20/20 | 6/20 | [0.145, 0.519] |

## Interpretation

The held-out wording produces model-dependent permissive behavior while all
three hardened conditions reject the tested escalation requests. This is
decision-only evidence, not live tool execution. It is stronger than the
action-layer replay for testing model behavior, but it does not establish
end-to-end committed external state.

No `429` or rate-limit error occurred. The only transient failures were five
gateway HTTPS EOFs, all recovered by `--resume`. The API key was supplied
interactively and was never written to the repository or result files; rotate
it after the experiment.

## Analysis artifacts

- `analysis/infocom_heldout_live20_quality.csv`
- `analysis/infocom_heldout_live20_overall.csv`
- `analysis/infocom_heldout_live20_dedup.jsonl`
