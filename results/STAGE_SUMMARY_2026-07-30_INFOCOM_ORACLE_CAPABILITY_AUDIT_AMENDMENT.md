# INFOCOM oracle-capability audit amendment (2026-07-30)

## Timing and scope

This amendment was written after all native model runs. It adds a read-only
source audit of the locally archived official AgentDojo implementation. It does
not rerun a model, change a frozen scenario, or reinterpret an existing outcome.

## Motivation

An earlier manuscript draft described prior agent-security benchmarks too
broadly as stopping at tool invocation. AgentDojo's official task interface can
inspect both the pre-task and post-task environment, and some tasks instead use
function traces. The comparison must therefore distinguish final-state
inspection from the authorization-relative and temporal properties encoded by
PSEBench.

## Added audit

The audit will record the archived AgentDojo revision, enumerate the official
v1 injection-task `security` implementations, and test source-backed capability
predicates. The predicates cover access to post-state and traces, plus explicit
representations of a current versioned authorization envelope, a check-to-commit
state change, an exact-effect receipt, and a service-local linearization point.

Absence from the audited suite is not treated as an impossibility result.
AgentDojo can be extended with new task-specific state predicates. The result
only establishes what the archived benchmark tasks and evaluator explicitly
encode.

## Outputs

- `analysis/benchmark_oracle_capability_audit.csv`
- `analysis/benchmark_oracle_capability_task_inventory.csv`
- `analysis/benchmark_oracle_capability_integrity.csv`
