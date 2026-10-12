# Local 7B persistence audit correction

Before freeze, the installed-model list was reduced from three to two because
Gemma had not finished downloading. The 24 task definitions, prompts, decoding,
and outcome definitions were unchanged. The frozen schedule contains exactly
192 keys, matching 2 models × 24 tasks × 2 instruction conditions × 2 framings.
Its scope correctly says 192 calls, but max_calls remains a 288-call ceiling
and the original observer contains obsolete 288-row/576-ledger assertions.

The oversight was discovered during Qwen execution, before seeing aggregate
outcomes; two schema-error rows were already available to the independent
reviewer. This correction is not described as outcome-blinded. Preserve the
frozen protocol, original observer, and all raw rows.
The independently reparsing audit v2 validates 192 raw keys and 384 policy
branches, checks the hash of the original frozen observer, and discloses this
deviation. It does not change prompts, labels, candidates, or committed state.
The revised auditor is `analysis/audit_local_7b_persistence_v2.py`.
The exception applies only to protocol SHA-256
`099690c54c5050039543b3ba8eb213a1b04057cefba53dd4f58cbdbcbb7c42f3`.
The final audit includes both original and revised auditor hashes.

This remains an exploratory development experiment, not a confirmatory
held-out study. Gemma will require a separate amendment/run if installed.
