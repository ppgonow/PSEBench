# Native Tool-Call Protocol Probe (2026-07-16)

Two synthetic, non-benchmark requests were sent to the authorized
OpenAI-compatible endpoint before executing any PSEBench matrix unit.

| Requested alias | Native `tool_calls` | Expected probe calls | Text-only fallback | Result |
| --- | ---: | ---: | ---: | --- |
| GPT-5.5 | 1 | 1 | no | pass |
| Grok-4.5 | 1 | 1 | no | pass |

The prompt requested one `record_probe_token` call over a synthetic constant.
No tool was executed, no scenario or attack content was supplied, and these two
requests are not experimental observations. The probe establishes protocol
behavior for the requested aliases only; it does not authenticate backend model
identity or establish task completion, attack behavior, or policy effectiveness.
