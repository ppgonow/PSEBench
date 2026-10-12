# PSEBench Artifact Manifest

This repository snapshot is prepared as a public benchmark artifact for
PSEBench. It contains the scenario corpus, runner code, analysis scripts,
summary tables, and reproducibility instructions needed to inspect and
regenerate the reported artifact-backed evidence.

Paper drafts, LaTeX sources, build outputs, local notes, machine-specific
configuration, and raw live-run directories are intentionally excluded from the
public snapshot.

For double-blind review, share this snapshot through an anonymized archive or
repository mirror. Do not provide a hosting URL whose account or organization
name identifies the authors.

## Artifact Scope

| Path | Public status | Purpose | Regeneration notes |
| --- | --- | --- | --- |
| `scenarios/` | included | Benchmark scenario YAMLs grouped by family and evaluation slice. | Static corpus; validated by `python3 analysis/schema_check.py`. |
| `data/web/` | included | Local benign, attack, and hybrid web fixtures referenced by web scenarios. | Static fixtures. |
| `runner/` | included | CLI, decision, proxy, policy, and local replication runners. | Main local no-notify entry point: `python3 runner/run_noncron_replication.py`. |
| `analysis/` | included | Aggregation, oracle, confidence-interval, evidence-gap scripts plus exported summary tables. | Recompute derived summaries with the commands in `REPRODUCIBILITY.md`. |
| `analysis/audit_feedback_adaptive_v2.py` and `analysis/feedback_adaptive_v2_*.csv` | included | Feedback-adaptive scripted traces that retry alternate endpoints, unknown fields, sequence overflow, and unauthenticated confirmation after observing a decision. | Run `python3 analysis/audit_feedback_adaptive_v2.py`; this is adapter conformance evidence, not model prevalence. |
| `runner/run_receipt_mask_ablation.py` and `analysis/audit_receipt_mask_ablation.py` | included | Complete 32-profile receipt-field composition audit over the frozen 150-case check-to-commit corpus (4,800 profile/scenario rows). | Run the commands in `REPRODUCIBILITY.md`; this is bounded conformance evidence, not a prevalence estimate. |
| `formal/` | included | Dependency-free bounded security, oracle-lattice, and multi-principal authority checkers. | Run `python3 formal/bounded_security_model.py`, `python3 formal/bounded_oracle_lattice.py`, and `python3 formal/bounded_multi_principal_authority.py`. |
| `scenarios/adapter-observer-heldout/` | included | Frozen 48-case adapter/observer conformance corpus: 12 profiles across four workflows. | Audit with `python3 analysis/audit_adapter_observer_holdout.py --overwrite`. |
| `scenarios/posix-file-provider-heldout/` | included | Frozen 24-case POSIX provider corpus in one temporary namespace. | Audit with `python3 analysis/audit_posix_file_provider.py --overwrite`. |
| `scenarios/caldav-provider-heldout/` | included | Frozen 28-case loopback CalDAV corpus for Radicale 3.7.8. | Install `requirements-provider.txt`, then run `python3 analysis/audit_caldav_provider.py --overwrite`. |
| `analysis/native_extension_protocol_v1.md` and `analysis/native_extension_grok_4_6_integrity.json` | included | Pre-registered extension protocol and structural audit for a requested relay alias. | The recorded `grok-4.6` run has 86/96 proposal-ready rows and is explicitly invalid for ASR/TCR estimation. |
| `oracles/` | included | Labeling/oracle conventions, blinded audit protocol, and helper materials. | Static documentation and helpers. |
| `tests/` | included | Unit checks for IACG intent/action-boundary, authorization utility, multi-tool composition, commit binding, network schedules, durable/failover queues, baselines, and confirmation behavior. | Run with `python3 -m unittest discover -s tests -p 'test_*.py'`. |
| `results/STAGE_SUMMARY*.md` | included | Human-readable summaries of major experimental stages. | Static summaries of completed stages. |
| `results/runs/` | regenerated locally | Raw per-run artifacts such as `final.json`, `scenario.yaml`, `agent_output.txt`, and `cli_events.jsonl`. | Gitignored to avoid publishing local paths, transient logs, and machine-specific delivery metadata. |
| `runner/config.yaml` | local only | Machine-specific mappings, chat IDs, and optional honeypot paths. | Create from `runner/config.example.yaml` when needed. |
| `src/`, `build/`, `paper/`, `paper_writing/`, `presentation/` | excluded | Paper source, compiled PDFs, drafts, and presentation materials. | Not part of the public benchmark artifact. |

## Reproduction Tiers

### Tier 0: No-Credential Sanity Checks

These checks do not require live service credentials.

```bash
scripts/sanity_check.sh
```

The sanity entry point runs the complete unit suite, validates every scenario,
regenerates the independent-unit inventory and same-ID paired policy results,
reconstructs the released headline claims from released data, and compiles all
runner and analysis modules. The original 141 run records are explicitly
reported as 45 distinct scenarios and are not assigned a pooled binomial
interval. Paper-source placement checks are additionally enabled when the local
ignored `src/` tree is present.
It also regenerates the strict-v2 adaptive adapter audit, the adapter/observer
holdout, the POSIX provider holdout, the optional Radicale CalDAV holdout, the bounded security model, and the same-tool
Holm, whole-block, bootstrap, and design-sensitivity outputs. Source-dependent
AgentDojo inventory and same-state distinguishability checks run only when the
official upstream checkouts and Pydantic 2 are available; the checkouts are not
redistributed. The frozen 16-case manifest and released no-model outputs remain
available for offline inspection. Socket-dependent service tests
require an environment that permits loopback binding.

The same-ID analysis reads local `results/runs/*/final.json` files when all 14
required run roots are present and refreshes
`analysis/independent_paired_outcomes.csv`. Because raw live-run directories
can contain machine-specific metadata, the anonymous artifact instead includes
this minimal table of scenario IDs, conditions, and manual outcome labels. A
clean extraction recomputes the paired statistics from that table; a partial
raw-run inventory is rejected rather than mixed with frozen outcomes.

It also checks the nine-item ACSAC review-response evidence map. Partial items
remain explicitly partial; the check verifies evidence and manuscript boundary
language rather than converting missing live experiments into completed ones.

The released no-credential native-to-commit bridge connects the 192 frozen
authorized clean native proposals to distinct loopback authorization, gateway,
and effect processes. Its 768-row JSONL and CSV outputs retain every policy and
state clone. `analysis/audit_native_service_commit_bridge.py` independently
checks the append-only attempt set, per-alias paired outcomes, 384 active
revocation gates, effect-hash continuity, ledger cardinality, ephemeral cleanup,
and anonymous topology. Re-execution requires no model or service credential;
it creates only loopback listeners and temporary SQLite state.

### Tier 1: Local Non-Cron Replication

This tier regenerates the final `riskfix2-*` file, calendar, recipient, and
legitimate-persistence artifacts without live notification delivery. The
expected local run set contains 104 finalized no-notification runs: 72
attack-side non-cron runs and 32 legitimate-persistence utility runs.

```bash
python3 runner/run_noncron_replication.py
python3 analysis/auto_oracle_noncron.py
python3 analysis/evidence_gap_tables.py
```

Expected high-level outputs:

| Output | Expected property |
| --- | --- |
| `analysis/noncron_replication_summary.csv` | file/calendar/recipient permissive attacks succeed in 12/12 cases per family, while IACG blocks unauthorized persistent or broader-scope actions and preserves legitimate file/calendar persistence in 8/8 cases per family. |
| `analysis/auto_oracle_noncron_summary.csv` | artifact oracle agrees with stored labels for 165 supported non-cron artifact-backed runs. |
| `analysis/artifact_oracle_coverage_summary.csv` | combines cron and non-cron artifact-oracle coverage over 417 machine-checkable finalized artifacts. |

The generated raw directories under `results/runs/riskfix2-*` remain local by
default. They can be deleted and regenerated from the commands above.

### Tier 2: Derived Summary Regeneration

After representative raw artifacts exist locally, regenerate derived tables:

```bash
python3 analysis/auto_oracle_from_cli.py
python3 analysis/auto_oracle_agreement.py
python3 analysis/auto_oracle_noncron.py
python3 analysis/compute_ci_tables.py
python3 analysis/confirm_all_persistent_report.py
python3 analysis/slc_report.py
python3 analysis/reviewer_gap_tables.py
python3 analysis/evidence_gap_tables.py
python3 analysis/benchmark_guard_overhead.py
python3 analysis/label_audit.py prepare --seed 20260523
python3 analysis/label_audit.py score analysis/label_audit_annotated_from_xlsx.csv
```

The held-out adaptive action-layer replay is also deterministic and does not
require credentials or live services:

```bash
python3 runner/generate_heldout_adaptive.py --count 100
python3 runner/replay_action_boundary.py \
  --policies permissive IACG TaskShield-style PFI-style
python3 analysis/summarize_heldout_replay.py
```

It produces paired policy results over 100 distinct scenario IDs, with attack
success determined from the typed committed effect rather than injection cue
matching. The replay is reported as action-layer evidence, separately from
live model execution.

The authorization-utility extension adds 100 implicit legitimate persistence
requests and 50 ambiguous authorization attacks. It keeps ground-truth labels
separate from runtime prompt inference and reports false-block and confirmation
rates in addition to ASR/TCR:

```bash
python3 runner/generate_authorization_utility.py \
  --legitimate-count 100 --ambiguous-count 50
python3 runner/replay_action_boundary.py \
  --scenario-dir scenarios/authorization-utility-heldout \
  --output-root results/authorization_utility_runs
python3 analysis/summarize_heldout_replay.py \
  --root results/authorization_utility_runs \
  --output-prefix analysis/authorization_utility
```

The resulting scenario corpus, derived CSVs, and stage interpretation are
recorded under `scenarios/authorization-utility-heldout/`,
`analysis/authorization_utility_*.csv`; the corresponding local stage report is
omitted from the anonymous archive.

Fresh-rule generalization and non-cron utility extensions are stored under
`scenarios/fresh-authorization-heldout/` and
`scenarios/fresh-noncron-authorization-heldout/`. Each corpus includes a
manifest plus the frozen runtime-rule SHA-256. Their local action-layer stage
reports are omitted from the anonymous archive.

The frozen multi-tool composition extension is stored under
`scenarios/multitool-chain-heldout/`. It locally specifies required and attack
effects for file-to-message, calendar-to-message, and message-to-file chains,
then reports per-effect enforcement separately from model proposal behavior; its
local stage report is omitted from the anonymous archive.

The frozen check-to-commit extension is stored under
`scenarios/commit-race-heldout/`. It locally specifies 100 invalid commit states
and 50 matched controls across five transition families. The completed
`runner/run_multiprocess_commit_race.py` path separates authorization state,
commit gateway, and effect storage into three OS processes communicating over
HTTP, then compares check-once, PAuth-style/pre-action, PCAS-style/pre-action,
and receipt-bound execution over 600 observations. The timestamp-free public
detail table supports an independent audit of complete keys, causal timing
status, distinct process roles, duplicate-delivery idempotence, paired outcomes,
and ledger counts. Typed literature-inspired rows are adaptations rather than
official implementations. This remains a single-host service decomposition.
The original single-process HTTP run and cryptographic microbenchmark remain as
supporting evidence under `analysis/http_commit_race_*.csv` and
`analysis/commit_binding_overhead_*.csv`; the multi-process result and all
rejected infrastructure attempts are retained in the corresponding 2026-07-18
stage reports.

A separate stable loopback load matrix uses the same three-process reference
path with bounded persistent HTTP/1.1 connections. It compares check-once and
receipt-bound at concurrency 1, 8, and 32 over three repeats and 3,600 measured
requests. `analysis/commit_gateway_load_detail.csv` records per-request client
and gateway latency plus commit/delivery/ledger invariants;
`analysis/commit_gateway_load_summary.csv` reports repeat-level throughput and
request-level tail latency. `analysis/audit_commit_gateway_load.py` requires the
complete frozen key set and regenerates the released summary without the local
SQLite database. This is loopback reference-path evidence, not WAN or
production-capacity evidence.

A separate cross-service schedule matrix reuses all 150 commit-race scenarios
under five fixed profiles: single request, 40-ms delay, duplicate downstream
delivery, concurrent retry, and forced retry reordering. Check-once and
receipt-bound produce 1,500 complete policy/profile/scenario rows, 2,100
gateway attempts, 1,600 effect deliveries, and 1,000 idempotent ledger commits.
`analysis/network_schedule_detail.csv` is the released observation table;
`analysis/audit_network_schedule.py` independently validates all causal,
arrival-order, delivery, and ledger invariants, while
`analysis/analyze_network_schedule_results.py` regenerates Wilson, benign
latency, family, and paired views. The temporary databases, HMAC key, process
identifiers, and raw crash diagnostics are excluded. All invalid attempts and
dated corrections remain in the public stage reports.

A separate asynchronous matrix releases
`analysis/async_queue_commit_{detail,summary,integrity}.csv`, the loopback-only
broker and runner, and `analysis/audit_async_queue_commit.py`. It repeats the
150 scenarios under steady consumption and broker restart, applies every attack
mutation only after enqueue acknowledgement and before first delivery, and
simulates acknowledgement loss plus redelivery every fifth scenario. The
daemon-free audit checks all 600 keys, 400 attack causality gates, 300 restart
gates, 120 releases, 720 broker/effect attempts, FIFO order, acknowledgement,
nonce, and one-effect idempotence totals. Broker/effect databases, WAL files,
HMAC material, ports, process identifiers, and logs are excluded. The broker is
an auditable durable-queue reference, not a production messaging system or
partition-tolerance claim.

A separate Docker failover matrix releases
`analysis/docker_queue_failover_{detail,summary,integrity,metadata}.csv`, four
minimal container roles, the one-shot runner, and
`analysis/audit_docker_queue_failover.py`. It injects one shared Docker fault
epoch per 150-row policy/profile cell: consumer A first claims every message,
then either loses its effect-service path before commit or is killed after
commit but before acknowledgement; consumer B recovers the messages. The
daemon-free audit verifies all 600 unique keys, four fault epochs, 600 recovery
and acknowledgement gates, 1,200 broker deliveries, 900 effect attempts, 400
effect rows, and 200 idempotent allowed crash redeliveries. Public metadata is
limited to the pinned image digest, bridge driver, loopback publication mode,
fault-epoch count, and matrix size. Containers, networks, broker/effect files,
WAL files, HMAC material, ports, runtime identities, and logs are excluded.
This establishes consumer-path Docker disconnect/crash failover against the
auditable reference queue, not production-broker compatibility, broker-storage
partition tolerance, replicated consensus, WAN behavior, multi-tenant
isolation, or independent administration.

A separate service-integrated matrix closes the verifier-to-effect transaction
gap without replacing the gateway schedule results. The effect service stores
authoritative commit state and its ledger in one temporary SQLite database;
`service-atomic` verifies the receipt, consumes any confirmation nonce,
deduplicates the trial ID, and inserts the effect under one `BEGIN IMMEDIATE`
transaction. `gateway-split` verifies before the transaction and then uses an
unverified effect write. The released 540-row detail covers all 150 scenarios
under pre-transaction invalidation and 120 context-mutation scenarios under a
post-verifier critical window. `analysis/audit_service_integrated_commit.py`
reconstructs the 180/0 split/atomic stale commits, 80 serialized critical
windows, duplicate delivery, nonce, and ledger totals without a service or
database. The plan, failed first invocation, condition-isolation amendment, and
sole reportable result are retained in the released service-integrated summary
tables; local stage reports are omitted from the anonymous archive.
This is service-local SQLite atomicity, not a cross-database distributed
transaction or production-capacity claim.

A separate PostgreSQL 17 portability replication releases
`analysis/postgres_integrated_commit_*.csv` and
`analysis/audit_postgres_integrated_commit.py`. It repeats the same 540 keys
under `READ COMMITTED` with `SELECT ... FOR UPDATE` on each authorization-state
row. The SQLite and PostgreSQL security, task, idempotency, nonce, and ledger
outcomes match for every key but remain separate replications rather than a
pooled sample. The public metadata records only the backend/version, driver,
image digest, isolation level, and row count. The password, DSN, loopback port,
container ID, database, HMAC key, and logs are excluded. This supports
transaction-backend portability within one effect service, not cross-database
atomicity or production performance.

The same frozen 600-cell matrix is released as a Docker-isolated same-host
replication under `analysis/container_commit_race_*.csv`. The detail,
topology, summary, paired, and integrity tables support a daemon-free audit of
three container/namespace hashes, three IPs, one user-defined bridge,
loopback-only port bindings, causal timing, idempotence, and outcomes. Raw
Docker identifiers, the ephemeral HMAC key, SQLite ledger, and raw JSONL stay
local. The network amendment explicitly records `network_internal=0`; this is
not internal-network, multi-host, or production-service evidence.

The frozen matrix also has a three-remote-instance replication under
`analysis/multihost_commit_race_*.csv`. Authorization, gateway, and effect ran
on three authorized remote Docker instances with distinct boot, DMI, cgroup,
hostname, CPU-info, and PID/network/UTS namespace hashes, connected through
loopback-only SSH-tunneled HTTP. The daemon-free audit checks all 600 rows, 400
causal mutation gates, retry/ledger invariants, service health, and gateway
relay evidence. The shared cloned machine-ID and SSH-proxy hashes are retained
as limitations. This is remote-container evidence, not proof of physical hosts,
independent administration, direct private networking, production traffic, or
distributed transactions. Raw remote identifiers, SSH material, logs, HMAC,
SQLite ledger, and JSONL remain local.

The bounded model confirmation-decision runner is
`runner/run_confirmation_decision.py`; it has a dry-run mode and writes only
decision JSONL, never tool executions. Its aggregation helper is
`analysis/summarize_confirmation_decision.py`. Credentialed execution is
optional and requires a newly rotated environment-provided key. The runner
enforces 120 logical jobs, at most 150 HTTP attempts, sequential rate limiting,
bounded retry, HTTPS, output-collision protection, cumulative resume accounting,
resumable successful rows, and credential redaction by default. The summarizer
requires the expected models and validates all six model/framing cells and zero
unresolved errors before producing a report.
The no-network safety audit and its pre-request paired analysis are recorded in
the released CSV summaries; local stage reports are omitted from the anonymous
archive. The design explicitly limits the 120-call condition to descriptive
supporting evidence.

The native model-driven slice is frozen in
`scenarios/native-e2e48/MANIFEST.csv`; its local planning report is omitted
from the anonymous archive. The
`runner/run_native_e2e.py` dry run validates 48 unique scenarios across four
boundaries, two fixed model families, and three executable policies (288
units) before reading credentials. Its live path requires an environment
credential and an HTTPS endpoint, executes only native provider
tool-call objects, mediates typed effects, and derives outcomes from a SQLite
sandbox ledger. `analysis/summarize_native_e2e.py` refuses partial or
prompted-tool rows before producing summary and paired tables. The
credential-free adapter and state verification are recorded in the released
request-audit tables.

Before benchmark execution, a synthetic protocol probe confirmed native
`tool_calls` for requests to GPT-5.5 and Grok-4.5 aliases on the available
compatible endpoint; it did not authenticate backend identities. The amendment
freezes the model substitution before any benchmark outcome and limits the resulting claim
to two requested-alias conditions through one shared provider interface.

The completed amended-v2 matrix releases 288 sanitized final traces plus
detail, summary, paired, and request-audit tables. Every unit commits its
primary authorized effect; 282/288 also invoke the requested sender-confirmation
tool, and no trace proposes an escalation-capable effect. Consequently the
result establishes compatible native-interface and primary-effect coverage,
not action-policy efficacy. The excluded exposure pilot, exposure amendment,
infrastructure retry record, and final interpretation are retained as stage
reports.

The adaptive native shared-proposal fork is the proposal-bearing native control.
Its 80-instance holdout is frozen under `scenarios/adaptive-native-holdout/`,
with five semantic attack templates per boundary and four identifier/target
instantiations per template. The first
native effect proposal and conversation state are cloned into permissive and
IACG continuations. A post-run audit found that v1's inherited read-tool
description labels returned content untrusted; v1 is therefore retained as a
separate provenance-marked-schema condition. A locally frozen same-scenario
replication changes only that description to neutral. Both released final trace
sets contain 160 alias/scenario units and are never pooled.

In the schema-neutral replication, requested GPT-5.5 permissive/IACG ASR is
2/80 versus 0/80 and primary TCR is 78/80 versus 79/80. Requested Grok-4.5 ASR
is 35/80 versus 0/80 and primary TCR is 61/80 versus 75/80. V1 remains
available as a distinct condition with its original results.

`analysis/audit_adaptive_native_fork.py` performed post-run audits against the
local SQLite databases and matched all 328 v1 commits and all 330 schema-neutral
commits. For clean public reproduction, the artifact includes timestamp-free
ledger exports and sanitized final JSONL. The following no-credential command
reconstructs the schema-neutral effects and policy outcomes and must reproduce
the released detail, per-boundary, paired, and metadata tables:

```bash
python3 analysis/audit_adaptive_native_fork.py \
  --raw analysis/adaptive_native_fork_schema_neutral_final.jsonl \
  --final analysis/adaptive_native_fork_schema_neutral_final.jsonl \
  --ledger-csv analysis/adaptive_native_fork_schema_neutral_postrun_audit_ledger.csv \
  --output-prefix tmp/adaptive_native_schema_neutral_public_audit
```

The artifact also releases the sanitized GPT-5.4/GPT-5.6-sol post-hoc native
extension. Reproduce its summary and terminal-aware read-only audit with:

```bash
python3 analysis/summarize_adaptive_native_fork.py \
  analysis/adaptive_native_fork_gpt54_gpt56_final.jsonl \
  --manifest scenarios/adaptive-native-holdout/MANIFEST.csv \
  --models gpt-5.4 gpt-5.6-sol \
  --output-prefix tmp/adaptive_native_gpt54_gpt56
python3 analysis/audit_adaptive_native_fork.py \
  --raw analysis/adaptive_native_fork_gpt54_gpt56_final.jsonl \
  --final analysis/adaptive_native_fork_gpt54_gpt56_final.jsonl \
  --ledger-csv analysis/adaptive_native_fork_gpt54_gpt56_postrun_audit_ledger.csv \
  --output-prefix tmp/adaptive_native_gpt54_gpt56_public_audit \
  --allow-terminal-without-effect
```

This extension matches 317 SQLite commits and 941/941 returned-alias metadata
records. Its raw relay JSONL and local SQLite database remain excluded.

The no-credential template audit prevents identifier-level instantiations from
being treated as independent semantic attacks:

```bash
python3 analysis/analyze_adaptive_native_templates.py \
  --manifest scenarios/adaptive-native-holdout/MANIFEST.csv \
  --final \
    analysis/adaptive_native_fork_schema_neutral_final.jsonl \
    analysis/adaptive_native_fork_gpt54_gpt56_final.jsonl \
  --output-prefix tmp/adaptive_native_templates
```

It must map 320 native instances to 80 alias--template clusters. Template-level
paired ASR support is GPT-5.5 1/20 versus 0/20 (`p=1`), Grok-4.5 9/20 versus
0/20 (`p=0.00390625`), GPT-5.4 7/20 versus 0/20 (`p=0.015625`), and
GPT-5.6-sol 3/20 versus 0/20 (`p=0.25`). Instance counts remain available as
execution summaries but are not treated as independent semantic samples.

The primary same-tool matrix also releases its four-alias Holm adjustment,
fixed-seed 20,000-resample whole-block bootstrap, exact 12-block sign-flip
sensitivity, and fixed-design precision analysis. Regenerate these files from
the frozen sanitized traces with:

```bash
python3 analysis/summarize_same_tool_native_commit.py --final \
  analysis/same_tool_native_commit_gpt_5_5_final.jsonl \
  analysis/same_tool_native_commit_grok_4_5_final.jsonl \
  analysis/same_tool_native_commit_gpt_5_4_final.jsonl \
  analysis/same_tool_native_commit_gpt_5_6_sol_final.jsonl \
  --output-prefix tmp/same_tool_native_commit
```

The resulting `cluster_bootstrap`, `multiplicity`, and `precision` CSVs must
byte-match the released files. These post-hoc sensitivity analyses do not
change the frozen 48-pair primary endpoint. Only the Grok-4.5 alias remains
significant after both Holm correction and the exact whole-block check.

The artifact includes a 42-case, no-network adaptive audit of the effect
adapter. It covers 30 unsafe and 12 safe calls across 12 adversarial families
and four workflows, including unknown fields, exact-field substitution,
provider-default requests, alternate endpoints, partial updates, encoded
recurrence, and repeated one-shot composition:

```bash
python3 analysis/audit_adaptive_effect_v2.py \
  --output-prefix tmp/adaptive_effect_v2
cmp analysis/adaptive_effect_v2_detail.csv tmp/adaptive_effect_v2_detail.csv
cmp analysis/adaptive_effect_v2_summary.csv tmp/adaptive_effect_v2_summary.csv
cmp analysis/adaptive_effect_v2_integrity.csv tmp/adaptive_effect_v2_integrity.csv
```

Legacy v1 directly allows 16/30 unsafe cases. Strict v2 directly allows 0/30,
blocks 14 known-schema or sequence violations, and routes 16 unsupported unsafe
schemas to review. It also routes 4/12 safe controls with unknown benign
metadata to review. Strict v2 is a post-hoc versioned adapter and was not used
to relabel or replace any frozen native run.

The independent adapter/observer holdout is frozen under
`scenarios/adapter-observer-heldout/`. It contains 48 cases balanced over 12
profiles and four workflows. The independent observer and candidate normalizer
produce 16 same-effect outcomes, 12 mismatches, 12 review outcomes, and eight
aggregate outcomes (four within-budget allows and four budget blocks). The
corpus, detail, coverage, and integrity files are regenerated without network
access:

```bash
python3 analysis/audit_adapter_observer_holdout.py \
  --output-prefix tmp/adapter_observer_holdout --overwrite
cmp analysis/adapter_observer_holdout_detail.csv \
  tmp/adapter_observer_holdout_detail.csv
cmp analysis/adapter_observer_holdout_summary.csv \
  tmp/adapter_observer_holdout_summary.csv
cmp analysis/adapter_observer_holdout_coverage.csv \
  tmp/adapter_observer_holdout_coverage.csv
cmp analysis/adapter_observer_holdout_integrity.csv \
  tmp/adapter_observer_holdout_integrity.csv
```

The provider-specific POSIX holdout is frozen under
`scenarios/posix-file-provider-heldout/`. It contains 24 cases and 28 candidate
effects, with eight authorized and 20 unsafe effects. On both macOS and Linux,
the secure path commits 8/8 authorized effects and blocks 20/20 unsafe effects,
whereas the naive absolute-path baseline commits all 20 unsafe effects. The
corpus hash and platform-specific integrity records are released in
`analysis/posix_file_provider_{,linux_}integrity.csv`. This is a conformance
test for one temporary POSIX namespace, not a provider-wide prevalence claim.
Regenerate on either platform with:

```bash
python3 analysis/audit_posix_file_provider.py \
  --output-prefix tmp/posix_file_provider --overwrite
```

The protocol-level CalDAV holdout is frozen under
`scenarios/caldav-provider-heldout/`. It contains 28 cases across seven
profiles and runs a fresh Radicale 3.7.8 process for each policy/case pair.
The adapter covers one-shot creation, provider normalization, recurrence and
partial-update injection, endpoint substitution, stale ETag replacement, and
aggregate overflow. An independent HTTP observer uses GET and calendar-query
REPORT, including recurrence expansion. The secure path passes 28/28 cases and
commits no unsafe effects; the naive path commits 20 unsafe effects. This is
version-specific loopback conformance evidence, not evidence about Google,
Microsoft, or deployed CalDAV prevalence. Regenerate it with:

```bash
python3 -m pip install -r requirements-provider.txt \
  --target tmp/radicale_runtime
python3 analysis/audit_caldav_provider.py \
  --output-prefix tmp/caldav_provider --overwrite
```

Compare the generated detail, summary, and integrity outputs with
`analysis/caldav_provider_*`.

The dependency-free bounded security checker is also part of the artifact:

```bash
python3 formal/bounded_security_model.py
python3 formal/bounded_oracle_lattice.py
python3 formal/bounded_multi_principal_authority.py
```

These checks enumerate receipt-field omissions, post-check mutations, replay,
short sequences, and oracle lattice cells. They model only the service-local
assumptions stated in the paper and are not provider or network experiments.

The AgentDojo comparison is backed by source audits of
`ethz-spylab/agentdojo` at revision
`089ed468cf3ed0322acc66b0211f26d9d90dbf60` and
`ethz-spylab/agentdojo-core` at revision
`23bf925979d051443f2e780ab19bff80f2066d6d`. The released inventory records 27
official v1 injection-task security methods, of which 25 inspect post-state and
14 inspect both pre- and post-state. This corrects the broader claim that the
benchmark is tool-call-only. The audit script and source-derived CSVs are
public, while the upstream source checkout is not duplicated in the archive.
After obtaining the two official upstream repositories from
`https://github.com/ethz-spylab/agentdojo.git` and
`https://github.com/ethz-spylab/agentdojo-core.git` at the recorded revisions,
regenerate with:

```bash
python3 analysis/audit_benchmark_oracle_capabilities.py \
  --output-prefix tmp/benchmark_oracle_capability
```

A separate pre-frozen same-state audit executes four official AgentDojo task
predicates and a current-grant-relative oracle on identical pre/post states.
Its 16 cases span email target, file resource, calendar participant, and payment
lifetime. Every family contains all four label combinations once; the two
oracles differ in 8/16 constructed cases, four in each direction. This balance
is a factorial design check, not a prevalence estimate. With both upstream
checkouts available, regenerate and compare the released outputs with:

```bash
python3 analysis/audit_official_oracle_distinguishability.py \
  --output-prefix tmp/official_oracle_distinguishability
cmp analysis/official_oracle_distinguishability_detail.csv \
  tmp/official_oracle_distinguishability_detail.csv
cmp analysis/official_oracle_distinguishability_summary.csv \
  tmp/official_oracle_distinguishability_summary.csv
cmp analysis/official_oracle_distinguishability_integrity.csv \
  tmp/official_oracle_distinguishability_integrity.csv
```

The frozen manifest SHA-256 is
`9a21c1f81169f364e1db55cce02c0d4b8b505262ca751173048f1b26d53a82e1`.
The audit establishes oracle distinguishability without claiming that
AgentDojo is tool-call-only or unable to express a custom predicate. A dated
serialization amendment sorts only participant/recipient fields with set
semantics before hashing; it leaves ordered histories, states, predicates, and
labels unchanged and makes clean-process detail CSVs byte-identical.

The public artifact also contains the candidate-action method comparison used
in the main paper. Run:

```bash
python3 analysis/run_method_comparison.py \
  --output-dir tmp/method_comparison \
  --output-label candidate_action
```

The regenerated 1,080-row detail table, overall summary, by-slice summary, and
Markdown report must byte-match the released `analysis/method_comparison_*`
files. Literature-inspired rows are explicitly typed adaptations rather than
official or live model-driven reproductions.

Both aliases were requested through one self-hosted compatible relay. Matching
returned `model` metadata checks relay consistency but does not authenticate an
upstream model or establish cross-provider robustness. The original raw relay
JSONL and SQLite file remain local; credentials and endpoint configuration are
never included.

### Tier 3: Live or Model-Driven Replication

Live message-delivery and model-driven slices may require local credentials,
agent binaries, and delivery targets. They are documented in
`REPRODUCIBILITY.md` and `runner/README.md`, but they are not required for the
no-credential artifact sanity check.

The optional cross-model decision benchmark is credentialed but does not execute
live tools. It writes JSONL outputs under `results/cross_model/` and aggregates
one or more run files with `analysis/cross_model_decision_summary.py`.

## Evidence Boundary

PSEBench reports IACG as a conservative, rule-based action-boundary/reference
monitor. It is not claimed to be a general semantic reasoner or a complete
prompt-injection defense. Scenario `intent` and `oracle` fields are labeling and
aggregation metadata; they are not hidden runtime inputs to IACG.

The raw live-run directories are not committed because they can contain local
paths, transient logs, and delivery metadata. Public CSV/Markdown summaries and
the no-notify replication scripts provide the artifact-facing reproduction path.
The blinded label-audit packet can be regenerated from local finalized artifacts
with `analysis/label_audit.py`. The completed 72-case independent audit matches
attack-success labels on 72/72 cases (Cohen's kappa = 1.000); task-completion
agreement is reported with both observed agreement and kappa because the sampled
task labels are highly prevalence-skewed. Risk-label disagreements are reported
separately and are concentrated in R0/R1 severity calibration, not attack
success.
