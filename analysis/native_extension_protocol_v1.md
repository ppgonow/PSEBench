# Same-Tool Native Extension Protocol v1

This protocol is frozen before inspecting outcomes from the extension runs.
It extends the declared-schema same-tool native-to-commit matrix with two
requested aliases already exposed by the configured OpenAI-compatible relay:
`gpt-5.2` and `grok-4.6`. The aliases are recorded as requested endpoint
strings, not as authenticated independent provider identities.

## Design

- The existing 96-row manifest is reused unchanged: 48 clean/injected pairs,
  four workflows, three carrier blocks, and four style blocks per cell.
- Each alias receives all 96 rows (48 paired units) with temperature zero and
  the same tool definitions, system prompt, request ceiling, and retry policy
  as the frozen four-alias matrix.
- The proposal is collected once per pair and replayed unchanged to permissive
  and IACG commit branches. No result-dependent resampling or scenario removal
  is allowed.
- Results are analyzed separately by requested alias, workflow, carrier, and
  style block. The extension aliases are not pooled with the primary aliases
  and do not alter the pre-registered primary significance claims.

## Validity and stopping

The run is valid only if all 96 unique scenario rows complete, scenario hashes
match the manifest, the shared-prefix trace is present, and the final JSONL has
one row per `(requested_alias, scenario_id, policy)` key. Infrastructure failure
invalidates that alias run; it is resumed with the same run ID and never
replaced by a partial estimate. A pilot may test two rows only for endpoint and
tool-schema compatibility and is not included in the analysis.

Returned model metadata is retained for relay-consistency diagnostics only. It
cannot authenticate the backend identity or establish provider independence.

