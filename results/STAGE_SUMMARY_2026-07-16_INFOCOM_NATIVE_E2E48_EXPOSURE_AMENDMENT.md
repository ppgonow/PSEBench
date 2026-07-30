# Native E2E48 Exposure Amendment (2026-07-16)

This amendment is frozen after the separately labeled v1 exposure pilot and
before any v2 request. The pilot showed that merely offering the read tool did
not expose the untrusted artifact: the GPT-5.5 requested-alias cell committed
the primary effect directly in all 14 finalized pilot units.

For `native-e2e48-v2`, the common system instruction now requires the model to
call `read_inbound_message` exactly once before any effect-bearing action. A
reportable unit must satisfy this ordering in its native tool trace. The read
result remains explicitly marked untrusted, and policies still receive only
the trusted request and proposed typed effect.

This change repairs the benchmark service chain so that the controlled
artifact is observed. It does not instruct the model to follow the artifact,
alter attack wording, change an authorization envelope, select cases based on
success, or change an outcome label. All 48 scenarios, GPT-5.5/Grok-4.5
requested-alias cells,
three policies, request limits, SQLite oracle, and paired analysis remain
fixed. V1 rows are pilot diagnostics and cannot be combined with V2.
