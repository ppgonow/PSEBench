# Extended No-API Baseline Matrix

This table compares deterministic PSEBench policies and method-family adaptations over the same candidate-action scenario slice.
It evaluates what each policy would do if the scenario-defined sensitive action were proposed; it does not re-run a live model.
It does not call model APIs and does not constitute official reproduction of third-party systems.

| comparator_id | comparator | comparison_status | evidence_tier | n | attack_n | attack_successes | task_successes | confirmations | asr | tcr | confirmation_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BASE-01 | Permissive execution | paper-baseline | local-deterministic-baseline | 135 | 110 | 110 | 135 | 0 | 1.000 | 1.000 | 0.000 |
| BASE-02 | Firewall persistent/scope block | paper-baseline | local-deterministic-baseline | 135 | 110 | 0 | 119 | 0 | 0.000 | 0.881 | 0.000 |
| BASE-03 | Confirm-all sensitive effects | paper-baseline | local-deterministic-baseline | 135 | 110 | 0 | 119 | 126 | 0.000 | 0.881 | 0.933 |
| BASE-04 | Shallow Lexical Comparator | paper-baseline | local-deterministic-baseline | 135 | 110 | 1 | 135 | 0 | 0.009 | 1.000 | 0.000 |
| CMP-02 | Untrusted-dependency confirmation | adaptation | local-policy-adaptation | 135 | 110 | 0 | 135 | 110 | 0.000 | 1.000 | 0.815 |
| CMP-03 | Task-scoped action envelope | adaptation | local-policy-adaptation | 135 | 110 | 0 | 135 | 0 | 0.000 | 1.000 | 0.000 |
| CMP-04 | Declarative policy monitor | adaptation | local-policy-adaptation | 135 | 110 | 0 | 135 | 0 | 0.000 | 1.000 | 0.000 |
| IACG | Intent-Action Consistency Guard | paper-method | local-deterministic-reference-monitor | 135 | 110 | 0 | 135 | 0 | 0.000 | 1.000 | 0.000 |
