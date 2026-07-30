# INFOCOM same-tool native-to-commit result (2026-07-21)

## Formal run

The frozen matrix completed once for the four pre-specified aliases. Each alias
received the same 48 semantic templates in paired clean and injected
conditions, giving 96 native units per alias and 384 units in total. Every unit
reached `proposal_ready`; no terminal, null-proposal, API-error, or selectively
repaired row was omitted.

The action function was identical within each clean/injected pair. Only its
security-relevant arguments could differ. The first native proposal and
conversation state were reused by the permissive and IACG branches rather than
resampled.

## Native same-tool results

The table reports the 48 injected units for each alias. Wilson intervals are
95% intervals. McNemar tests use the same 48 template IDs and compare
permissive with IACG without pooling aliases.

| Requested alias | Unsafe first proposals | Permissive ASR (95% CI) | IACG ASR (95% CI) | Permissive TCR | IACG TCR | ASR McNemar p |
|---|---:|---:|---:|---:|---:|---:|
| GPT-5.5 | 3/48 | 5/48 [0.045, 0.222] | 0/48 [0, 0.074] | 44/48 | 48/48 | 0.0625 |
| Grok-4.5 | 21/48 | 25/48 [0.383, 0.655] | 0/48 [0, 0.074] | 27/48 | 32/48 | 5.96e-8 |
| GPT-5.4 | 4/48 | 4/48 [0.033, 0.196] | 0/48 [0, 0.074] | 44/48 | 44/48 | 0.125 |
| GPT-5.6-sol | 4/48 | 5/48 [0.045, 0.222] | 0/48 [0, 0.074] | 44/48 | 45/48 | 0.0625 |

No clean condition produced an unsafe first proposal. The paired
clean/injected counts were 0 versus 3 for GPT-5.5, 0 versus 21 for Grok-4.5, 0
versus 4 for GPT-5.4, and 0 versus 4 for GPT-5.6-sol. The corresponding exact
McNemar p-values were 0.25, 9.54e-7, 0.125, and 0.125.

The pre-specified primary analysis treats the 48 same-template pairs per alias
as the paired units. Because four workflow instantiations share each of 12
carrier/style blocks, a dated post-hoc sensitivity analysis also applied an
exact sign-flip test to those blocks. The ASR p-values were 0.125, 0.0009766,
0.125, and 0.125 for GPT-5.5, Grok-4.5, GPT-5.4, and GPT-5.6-sol. Thus, the
Grok-4.5 result survives the conservative clustering check. The other aliases
show lower-frequency directional evidence but do not support an alias-specific
significance claim.

IACG never reduced the primary task relative to the paired permissive branch.
It completed four additional GPT-5.5 tasks, five additional Grok-4.5 tasks,
zero additional GPT-5.4 tasks, and one additional GPT-5.6-sol task. These TCR
differences are not claimed as significant.

## Native-to-commit bridge

All 192 clean native proposals were authorized at check time and therefore
entered the frozen commit bridge. Each proposal was cloned into
cached-pre-action/receipt-bound by stable/revoked state, yielding 768 unique
commit observations.

For every alias separately:

- cached-pre-action committed 48/48 stable effects and 48/48 stale revoked
  effects;
- receipt-bound committed 48/48 stable effects and 0/48 revoked effects;
- every commit indicator equaled its SQLite ledger-row count.

Across the four aliases, both policies completed 192/192 stable controls.
Cached-pre-action committed 192/192 stale revoked effects, whereas
receipt-bound committed 0/192. This bridge is conditional on an authorized
clean native proposal. It tests whether authorization survives a later version
change, not the population prevalence of that change.

## Integrity

- 384 native rows and 384 unique alias/scenario keys.
- 192 unique alias/template keys, each with one clean and one injected unit.
- 384/384 proposal-ready and 384/384 same-tool first proposals.
- 768 commit rows and 768 unique commit trial IDs.
- 576 total SQLite ledger rows, exactly matching the allowed commits.
- 1,558 HTTP attempts retained across all formal native units.
- Returned model metadata matched GPT-5.4, GPT-5.5, and GPT-5.6-sol exactly;
  the verified Grok-4.5 alias returned `grok-4.5-build`.
- Suite-specific schema validation reported zero missing required fields, zero
  missing recommended fields, and zero semantic issues.

## Interpretation and claim boundary

The experiment closes two reviewer-facing gaps. First, authorization-boundary
escalation remains observable when clean and injected conditions expose the
same parameterized action function, so the result is not caused by separately
named safe and unsafe tools. Second, an unmodified authorized native proposal
can become unsafe after revocation if a downstream service trusts a cached
pre-action decision; receipt-bound commit blocks the stale effect while
preserving the stable control.

The defensible cross-model claim is directional consistency, not a pooled model
effect: every alias has permissive-only stale or escalated commits and zero
IACG attack commits, while only Grok-4.5 is significant under both the primary
same-template test and the post-hoc block sensitivity analysis. Model aliases,
workflow cells, and repeated execution stresses remain separate evidence.

## Artifacts

- `analysis/same_tool_native_commit_gpt_5_5_final.jsonl`
- `analysis/same_tool_native_commit_grok_4_5_final.jsonl`
- `analysis/same_tool_native_commit_gpt_5_4_final.jsonl`
- `analysis/same_tool_native_commit_gpt_5_6_sol_final.jsonl`
- `analysis/same_tool_native_commit_detail.csv`
- `analysis/same_tool_native_commit_summary.csv`
- `analysis/same_tool_native_commit_paired.csv`
- `analysis/same_tool_native_commit_exposure_paired.csv`
- `analysis/same_tool_native_commit_cluster_paired.csv`
- `analysis/same_tool_native_commit_commit_detail.csv`
- `analysis/same_tool_native_commit_commit_summary.csv`
- `analysis/same_tool_native_commit_integrity.csv`
