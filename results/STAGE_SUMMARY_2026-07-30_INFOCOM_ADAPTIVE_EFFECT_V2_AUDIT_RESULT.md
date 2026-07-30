# INFOCOM adaptive effect-normalization v2 audit result (2026-07-30)

The deterministic audit contains 42 enumerated cases across four workflows and
12 adaptive families: 30 unsafe cases and 12 safe controls.

Legacy v1 directly allows 16/30 unsafe cases. The failures comprise four exact
declared-field substitutions that do not change the coarse typed boundary,
four unknown security-relevant fields, four provider-default requests, and four
two-call compositions that exceed a one-effect grant. This negative result is
retained and applies to the adapter used in the frozen native matrix.

Strict v2 directly allows 0/30 unsafe cases. It blocks 14 known-schema or
sequence violations and routes 16 unsupported-field or endpoint cases to
review. It directly allows 8/12 safe controls; the remaining four safe calls
carry unknown benign metadata and therefore also require review. No human
confirmation outcome is inferred from this result.

This audit establishes closure only for the enumerated, versioned schemas. It
does not establish completeness for undocumented provider behavior, hidden
side effects, or cross-service automation.

Artifacts:

- `runner/strict_effects_v2.py`
- `analysis/adaptive_effect_v2_detail.csv`
- `analysis/adaptive_effect_v2_summary.csv`
- `analysis/adaptive_effect_v2_integrity.csv`

