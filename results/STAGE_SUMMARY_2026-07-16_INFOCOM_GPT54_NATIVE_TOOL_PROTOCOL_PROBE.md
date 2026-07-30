# GPT-5.4 Requested-Alias Native Tool Protocol Probe (2026-07-16)

After the fixed 288-unit matrix and before the adaptive native development
pilot, one synthetic request was addressed to the `gpt-5.4` alias on the
self-hosted OpenAI-compatible relay.

The response contained exactly one native `tool_calls` object for the requested
`record_probe_token` function. It was not a prose or JSON-text fallback. No tool
was executed, no PSEBench scenario or attack content was sent, and this request
is excluded from every benchmark denominator and request count.

The result establishes protocol behavior for the requested alias only. It does
not authenticate the upstream model identity, measure attack behavior, or
establish policy efficacy.
