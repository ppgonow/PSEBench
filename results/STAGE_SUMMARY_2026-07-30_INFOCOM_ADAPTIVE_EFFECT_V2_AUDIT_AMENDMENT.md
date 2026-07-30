# INFOCOM adaptive effect-normalization v2 audit amendment (2026-07-30)

## Timing and scope

This amendment was written after the frozen native and normalization results.
No frozen result is rerun or overwritten. The adapter used by those experiments
remains `runner/same_tool_effects.py` and is reported as legacy v1.

## Motivation

The v1 adapter canonicalizes the declared fields but silently drops unknown
arguments and authorizes calls independently. An adaptive caller can therefore
hide a provider-relevant option in an unmodeled field or compose many permitted
one-shot calls into an aggregate effect that exceeds a single-effect grant.

## Added implementation and audit

A separate strict-v2 adapter will:

- require an exact, versioned argument schema for each supported endpoint;
- route unknown fields and unsupported endpoints to fail-closed review;
- retain canonical equivalence for declared fields and timezone variants;
- enforce a sequence-level cardinality budget before any effect is committed.

The deterministic red-team corpus will include unknown fields, alternate
endpoints, encoded recurrence, partial updates, provider defaults, repeated
one-shot composition, target expansion, and benign canonical variants. Each
case will be evaluated against both legacy v1 and strict v2. Legacy failures
will remain visible in the output.

## Claim boundary

Passing this corpus is conformance evidence for the enumerated adapter schemas.
It is not evidence that arbitrary provider side effects, undocumented API
behavior, or cross-service automation have been completely modeled.

## Outputs

- `analysis/adaptive_effect_v2_detail.csv`
- `analysis/adaptive_effect_v2_summary.csv`
- `analysis/adaptive_effect_v2_integrity.csv`

