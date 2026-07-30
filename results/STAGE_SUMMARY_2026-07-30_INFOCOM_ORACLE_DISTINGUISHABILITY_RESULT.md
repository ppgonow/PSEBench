# INFOCOM official-oracle distinguishability result (2026-07-30)

The frozen 16-case audit invoked four official AgentDojo v1 task classes from
revision `089ed468cf3ed0322acc66b0211f26d9d90dbf60`. For every case, the
official fixed-goal predicate and the current-grant-relative predicate received
the identical pre/post environment state.

Each of the email-target, file-resource, calendar-participant, and
payment-lifetime families contains all four label combinations exactly once:

- official goal satisfied and current grant safe;
- official goal satisfied and current grant violated;
- official goal not satisfied and current grant safe;
- official goal not satisfied and current grant violated.

Labels therefore differ in 8/16 frozen cases. Four differences are official
goal success under a containing current grant, and four are violations of the
current grant that do not satisfy the task's fixed attack goal. This balanced
rate follows the frozen factorial design and is not an estimate of prevalence.

The result shows that a fixed-goal predicate and a current-grant-relative
predicate answer different questions on the same state. It does not imply that
AgentDojo is tool-call-only or unable to express a custom authorization-aware
task. AgentDojo correctly evaluates its declared goals; PSEBench standardizes
the additional grant-relative comparison.

Integrity checks passed for 16 unique cases, two suites, four official task
classes, four families, 16 dual-oracle state pairs, and the frozen manifest
SHA-256 `9a21c1f81169f364e1db55cce02c0d4b8b505262ca751173048f1b26d53a82e1`.

Artifacts:

- `scenarios/oracle-distinguishability/official_agentdojo_v1.json`
- `analysis/audit_official_oracle_distinguishability.py`
- `analysis/official_oracle_distinguishability_detail.csv`
- `analysis/official_oracle_distinguishability_summary.csv`
- `analysis/official_oracle_distinguishability_integrity.csv`
- `tests/test_official_oracle_distinguishability.py`
- `results/STAGE_SUMMARY_2026-07-31_INFOCOM_ORACLE_DISTINGUISHABILITY_HASH_AMENDMENT.md`
