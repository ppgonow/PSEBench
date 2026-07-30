# INFOCOM oracle-capability audit result (2026-07-30)

The source audit examined AgentDojo official v1 at revision
`089ed468cf3ed0322acc66b0211f26d9d90dbf60`. It found 27 injection-task
`security` methods across four suites. Of these, 25 read `post_environment`, 14
read both `pre_environment` and `post_environment`, and the evaluator also
supports a trace-based fallback.

The result invalidates a blanket tool-call-only characterization. AgentDojo can
inspect task-specific final state. The audited tasks and evaluator do not,
however, explicitly encode a current versioned authorization object,
check-to-commit authorization invalidation, an authenticated exact-effect
receipt, or a service-local authorization/effect linearization point. These are
the narrower representational and temporal properties evaluated by PSEBench.

Absence is reported as "not explicit in the audited source," not as an
impossibility claim. A new AgentDojo task could add a custom post-state
predicate. Neither audited harness confirms arbitrary external-provider
post-state.

Artifacts:

- `analysis/benchmark_oracle_capability_audit.csv`
- `analysis/benchmark_oracle_capability_task_inventory.csv`
- `analysis/benchmark_oracle_capability_integrity.csv`

