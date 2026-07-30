# INFOCOM citation audit (2026-07-17, updated 2026-07-20)

## Scope

The compiled review paper cites 38 unique BibTeX keys. The audit extracted the
actual citation set from `build/main.aux`, checked that every key resolves under
IEEEtran BibTeX without a missing-entry warning, and compared publication
metadata with public primary records.

## Public-record checks

- arXiv API: 16/16 cited arXiv records returned a matching identifier, title,
  and author list.
- ACL Anthology: InjecAgent, Adaptive Attacks, and Task Shield official pages
  returned successfully; titles, authors, venues, years, and pages match.
- NeurIPS proceedings: Toolformer, AgentDojo, and Gorilla official pages match
  titles, authors, years, and page ranges.
- USENIX proceedings: Formalizing and Benchmarking Prompt Injection and StruQ
  official presentation pages returned successfully and match the cited venue.
- OpenReview: the ReAct ICLR record returned successfully.
- IEEE INFOCOM: four added records match the DBLP proceedings metadata and
  DOI records for prompt-security/resource optimization (2025), OpenRAN xApp
  authorization (2023), decentralized network-slice authorization (2024), and
  cross-domain capability access control (2025).
- Additional closest-work coverage includes ToolEmu (ICLR 2024), Breaking
  Agents (EMNLP 2025), two USENIX Security 2025 studies of web-enabled and
  taint-style agent risk, Agent-SafetyBench, multi-turn tool-use safety,
  verifiable tool use (ICSE NIER 2026), and the SAGA governance architecture.
- Final BibTeX/LaTeX compile: no missing database entry, undefined citation,
  undefined reference, overfull box, or LaTeX error.
- A 2026-specific recheck on 2026-07-20 verified all nine cited 2026 records
  against public primary metadata. Eight arXiv records match identifier, title,
  author list, and first-publication year; the ICSE NIER record matches Crossref
  and DBLP on title, six authors, 2026 venue, DOI, and pages 201--205.
- The PAuth/FORGE capability comparison was checked against both full texts.
  PAuth explicitly uses authenticated task envelopes and validates concrete
  operators/operands; FORGE explicitly evaluates Datalog over current substrate
  state at each candidate action. The table therefore marks those strengths and
  reserves `NS` for receipt version/expiry/nonce, retry idempotence, and atomic
  effect-service commit properties not specified or evaluated by those papers.

## Corrections made

1. Updated `arXiv:2602.16708` from the obsolete v1 title “Policy Compiler for
   Secure Agentic Systems” to the current v3 title “Formal Policy Enforcement
   for Real-World Agentic Systems,” and added Guy Amir to the author list.
2. Updated the related-work description from PCAS to the current FORGE system
   and its Datalog/reference-monitor design.
3. Corrected ReAct from the 2022 preprint year to its ICLR 2023 proceedings
   year and added its OpenReview URL.
4. Replaced abbreviated Task Shield and Prompt Flow Integrity author names with
   the public full names; Task Shield now uses its official ACL Anthology URL
   and DOI.
5. Corrected OpenAgentSafety's arXiv citation month/year to its first public
   release in July 2025 rather than the February 2026 revision date.
6. Protected the official capitalization of Toolformer, AgentDojo, Gorilla,
   LLM, APIs, and ReAct in IEEEtran BibTeX output.
7. Added the standard LaTeX `url` package so the OpenReview identifier and long
   reference URLs render safely.
8. Added four directly scoped IEEE INFOCOM references. The prose treats the
   prompt-security work as an edge/cloud security-performance comparison and
   the other three as network-authorization context, not as official agent
   baselines or evidence about check-to-commit invalidation.
9. Added eight directly scoped agent-security references and connected each to
   a specific benchmark, attack-surface, multi-turn, verification, or governance
   comparison in Related Work rather than citing them as an undifferentiated
   list.
10. Updated ToolEmu from its 2023 arXiv record to ICLR 2024, corrected
    Agent-SafetyBench to its December 2024 first-publication year, corrected the
    EMNLP page range and DOI for Breaking Agents, expanded the taint-style
    USENIX author list, and updated verifiable tool use to ICSE NIER 2026.

## Remaining human check

This is a metadata and reachability audit, not a substitute for rereading all
29 papers. Before upload, one author should verify that each nearby prose claim
is supported by the cited paper's method or findings, especially the current
FORGE, PAuth, Task Shield, Prompt Flow Integrity, and stored-injection
comparisons.
