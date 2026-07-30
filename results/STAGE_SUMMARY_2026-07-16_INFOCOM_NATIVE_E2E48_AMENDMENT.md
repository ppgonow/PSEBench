# INFOCOM Native E2E48 Pre-Execution Amendment (2026-07-16)

## Timing and reason

This amendment is frozen after a synthetic protocol-only compatibility probe
and before any of the 288 benchmark units. The probe contained no PSEBench
scenario, policy, attack, or outcome. It asked each candidate model to call a
single synthetic `record_probe_token` function and did not execute the tool.

The available authorized endpoint accepted requests under GPT-5.5 and Grok-4.5
aliases through the same OpenAI-compatible API but did not accept the previously
planned Claude alias. Both requested aliases returned exactly one native
`tool_calls` object in the
protocol probe, with no prompted-JSON fallback. The fixed model cells are
therefore amended from:

- `openai:gpt-5.5`
- `anthropic:claude-opus-4-6`

to:

- `openai:gpt-5.5`
- `openai:grok-4.5`

## Unchanged design

The 48 scenario IDs, four 12-case boundaries, three policies, 288 logical
units, six-turn cap, sequential request schedule, 1,800-attempt ceiling,
SQLite outcome oracle, Wilson intervals, paired McNemar tests, completeness
gate, retry policy, and no-post-hoc-exclusion rule are unchanged.

## Claim boundary

This is a same-endpoint requested-alias replication, not authenticated
cross-model-family or cross-provider evidence. Provider implementation and
gateway behavior are shared, and the endpoint response was not used to
authenticate backend identity. Results must be labeled GPT-5.5 and Grok-4.5
requested-alias conditions; they cannot support model-identity or
provider-independent robustness claims. The two
protocol-probe requests are excluded from all benchmark denominators and request
counts reported for the 288-unit matrix.
