# Frozen temporal diagnostic preflight

Frozen inputs: `tmp/temporal-diagnostic-20261011-v1/inputs.json`.
Frozen protocol: `tmp/temporal-diagnostic-20261011-v1/protocol.json`.
Runner: `analysis/run_temporal_diagnostic_20261011_v1.py`.

The matrix contains 24 templated development instances, each repeated in 16
conditions: 384 planned local calls. The six report contexts do not create
independent task families. There are no live exports or observed tool effects.
The order is fixed, not randomized, so time/order effects cannot be excluded.

The ordinary arm retains `approve`, `safe_fallback`, `reason`, and `evidence`.
The date-set arm returns `authorized_dates`, `proposed_dates`, `reason`, and
`evidence`; an offline subset check derives its comparison decision. This is a
bundled instruction, output-schema, and decision-rule intervention. Its effects
cannot be attributed separately to reasoning instructions or structured output.
Model extraction is not a trusted execution grant, ground truth, or post-state
observation. Extracted-set correctness must be reported separately from the
derived comparison decision; jointly incorrect sets can yield a correct decision.

Before inference, the generator independently recovered dates from explicit
authorization and expanded inclusive ranges, compared these with hidden grants,
verified the positive proposals and exactly-one-extra-date violations, checked
384 unique prompt hashes, and verified the local API model digest. Negative
controls rejected a forged grant, an integer approval, and an invalid date.

The frozen runner preserves response/error rows with fsync after each call,
uses no retries or replacement, and refuses to reopen an existing raw log.
An abrupt process kill can leave unattempted jobs absent; audit must retain the
384-job planned denominator and separately enumerate any missing jobs, without
resuming or replacing them. API calls remain confined to 127.0.0.1:11434.

Budget: at most 384 inference attempts, 98,304 accounted generated tokens,
14,400 seconds plus at most one in-flight 120-second timeout. Per-call generation
limit is 256 tokens. Calls with unavailable usage are charged 256 tokens. There
is no inference until parent authorization after independent preflight review.

SHA-256:

- Runner: `5df9feca00edbcc5ea46fa2bec5481ddb279107bac726e99c4dbba958ddb2996`
- Inputs: `50ca4974d6dd4ae81ea75ca99a8d7d373da31ac1f461b9960ec0c979cec5fd44`
- Protocol: `cf685b59b15f7af6e1e090c39107df828243515f068ebb5fe8827bc0f2953821`
- Model: `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`
