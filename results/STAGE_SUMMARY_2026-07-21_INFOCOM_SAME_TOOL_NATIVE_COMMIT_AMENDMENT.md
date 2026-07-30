# Same-tool native-to-commit generator amendment (2026-07-21)

The first corpus-generation attempt failed before writing any scenario,
manifest, conformance file, or result. `trusted_prompt` constructed prompt
strings for all workflows eagerly, so the first reminder scenario attempted to
read file-only arguments and raised `KeyError: path`.

This amendment permits one implementation-only correction: construct only the
prompt for the selected workflow. The frozen 4 x 3 x 4 x 2 matrix, text
templates, model aliases, policies, metrics, and acceptance gates do not
change. The empty output directories from the failed attempt are removed before
the first corpus is generated.
