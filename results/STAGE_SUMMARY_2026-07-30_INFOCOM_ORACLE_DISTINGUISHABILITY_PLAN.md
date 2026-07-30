# INFOCOM official-oracle distinguishability plan (2026-07-30)

## Timing and scope

This plan and its 16-case manifest were frozen before either oracle was run.
The audit is deterministic and uses no model, API, network target, or prior
model output. It does not alter any frozen PSEBench experiment.

## Question

Can an official fixed-goal security predicate and a current-grant-relative
predicate assign different labels to the same pre/post environment state?
This is a distinguishability question, not a claim that AgentDojo cannot be
extended with a new task predicate.

## Frozen design

The corpus contains four cases in each of four families:

- Workspace `InjectionTask0`: email target;
- Workspace `InjectionTask1`: deleted file resource;
- Workspace `InjectionTask2`: calendar participant;
- Banking `InjectionTask4`: scheduled-payment lifetime.

For each family, the manifest includes the official goal outcome, a neighboring
outcome, a containing current grant, and an excluding current grant. The same
official environment objects and identical pre/post state are supplied to the
official task's `security()` method and the PSEBench comparator. All four label
combinations are therefore represented by design rather than selected after
inspection.

## Evidence boundary

The audit can establish that the two oracle definitions are observationally
distinct on these frozen states. It cannot estimate attack prevalence, model
susceptibility, or the difficulty of adding an authorization-aware predicate
to AgentDojo. Official task classes and environment structures are loaded from
archived revision `089ed468cf3ed0322acc66b0211f26d9d90dbf60`.

## Frozen input

- `scenarios/oracle-distinguishability/official_agentdojo_v1.json`
- SHA-256: `9a21c1f81169f364e1db55cce02c0d4b8b505262ca751173048f1b26d53a82e1`

## Planned outputs

- `analysis/official_oracle_distinguishability_detail.csv`
- `analysis/official_oracle_distinguishability_summary.csv`
- `analysis/official_oracle_distinguishability_integrity.csv`
