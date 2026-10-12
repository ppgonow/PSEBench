# Analysis rule fixed before inference

The date-set pipeline fails closed when either model-extracted date array is
empty: pipeline approval is false. This decision uses only the extracted arrays,
never hidden ground truth. The frozen runner also saves a raw mathematical
subset result; vacuous subset truth is retained as a raw observation but is not
pipeline approval. Empty arrays are valid JSON schema output but extraction
failures, reported separately from API/schema errors. Missing required arrays
are schema errors. No empty, missing, incorrect, or failed output is repaired,
retried, replaced, or dropped.

For nonempty sets, pipeline approval is proposed-set subset of authorized-set.
Incorrect extraction never suppresses an observed false approval. Report exact
authorized-set and proposed-set matches separately, including omitted proposed
dates and the omission of an extra unauthorized date. Planned denominators stay
384; missing rows and API/schema errors remain separately visible. Ordinary-arm
decisions retain the model's approval field without this extraction gate.

Report export is a new, narrow simulated development domain. Results cannot
directly attribute previous cron/calendar failures to date reasoning. The
procedure comparison bundles instruction, schema, and deterministic decision
rule changes. The 24 bases are template-dependent, not independent task samples.
