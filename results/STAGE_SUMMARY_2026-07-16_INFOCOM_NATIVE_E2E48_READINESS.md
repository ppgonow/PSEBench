# INFOCOM Native E2E48 Execution Readiness (2026-07-16)

> **Historical pre-execution record, superseded.** The final run used the
> amended GPT-5.5/Grok-4.5 requested-alias cells and the v2 exposure protocol.
> See the model amendment, exposure amendment, infrastructure retry record,
> and final Native E2E48 result. Statements below describe readiness at this
> earlier stage, not the final evidence.

## Result status

The 288-unit native tool-calling matrix has not been executed against a live
provider. `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, and
`ANTHROPIC_BASE_URL` were unset during this stage. No API request was made and
no model outcome is reported.

## Frozen dry run

With all provider variables removed, `runner/run_native_e2e.py --dry-run`
validated:

- 48 distinct scenario IDs;
- 12 cron, 12 file, 12 calendar, and 12 recipient cases;
- fixed `openai:gpt-5.5` and `anthropic:claude-opus-4-6` model families;
- fixed `permissive`, `IACG`, and `confirm-all-persistent` policies;
- 288 logical model/policy/scenario units;
- six native tool-calling turns per unit and a cumulative 1,800-attempt ceiling.

A non-dry invocation without both credentials exits before creating a raw
JSONL or SQLite file. Both base URLs must be HTTPS. Credentials are read only
from environment variables and provider errors are redacted before storage.

## Protocol and state verification

Credential-free multi-turn provider simulations exercise both adapters:

- OpenAI-compatible `tool_calls` are parsed, executed, returned as role `tool`
  messages, and followed to a final assistant response.
- Anthropic `tool_use` blocks are executed, returned as `tool_result` blocks,
  and followed to a final assistant response.
- IACG blocks a durable file call while allowing and committing the one-shot
  file task; the permissive path commits both authorized and expanded-recipient
  message effects.
- Every allow decision adds exactly one SQLite row and every block or
  confirmation decision adds none.

`analysis/summarize_native_e2e.py` requires all 288 units, matching scenarios
across all alias/policy cells, zero unresolved provider errors, and at least one
native tool call per unit. It reconstructs effects from recorded tool names and
arguments, reloads each source scenario, recomputes primary-effect and attack
labels, and checks the released trace fields against each row's serialized
committed effects. It does not independently reopen the local SQLite database.

## Execution boundary

This stage establishes runner and analysis readiness only. It is not evidence
that either provider supports the declared interface at the configured
endpoint, that either model follows the injection, or that any policy changes
live ASR/TCR. Those claims require a complete run with newly rotated
credentials. The credential previously exposed in chat remains forbidden.
