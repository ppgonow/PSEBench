# INFOCOM manuscript coherence audit (2026-07-20)

## Scope

This audit reads the submission in order from title and abstract through the
conclusion. It checks terminology, notation, experiment ownership, statistical
units, protocol claims, and the correspondence among figures, tables, prose,
and released evidence.

## Narrative order

The paper now follows one evidence chain:

1. authorization-boundary escalation defines the general failure, with
   persistent state escalation as its durability case;
2. the threat model separates proposal escalation from commit invalidation;
3. PSEBench measures committed effects rather than suspicious text or tool use;
4. IACG separates request-side authorization inference from deterministic
   effect enforcement;
5. RQ1 establishes the hybrid-workflow phenomenon, RQ2 tests native proposals
   and same-proposal mediation, RQ3 tests whether effect authorization remains
   valid at commit under state changes and execution stresses, and RQ4 measures
   inference, confirmation, and performance costs;
6. related work, limitations, and the conclusion preserve the same comparison
   scope and evidence boundaries.

Figure 1 introduces the benchmark distinction, Table I separates tool, call,
and committed-effect evaluation units, Figure 2 presents the IACG enforcement
path, and Figure 3 summarizes the security--utility cells quantified later in
RQ4. Tables appear in the same order as the claims they support.

## Terminology and notation

- `target` is used for the security-relevant target field; `destination` is not
  used as a competing technical term.
- The versioned authorization envelope is written `A_u^v`; `(A_u,v)` is the
  algorithmic representation, and `A_a = eff(a)` is the normalized action
  effect.
- `IACG` names the full compiler--normalizer--checker--receipt path.
- `receipt-bound` names IACG's commit-verification mode when authorization and
  effect are already supplied.
- Prompt injection names a delivery vector; authorization-boundary escalation
  names the resulting authorization failure when an allowed tool's committed
  effect exceeds current authority.
- `permissive` performs no effect authorization; `check-once` caches an earlier
  allow; PAuth-style and PCAS-style are typed pre-action adaptations, not
  official reproductions.
- Remote replication is consistently described as `three-instance
  SSH-relayed`; it is not presented as direct private networking or independent
  administration.

## Enforcement and deployment boundary

IACG is positioned as a runtime effect-authorization mechanism, not a networking
protocol. Its enforcement unit is the normalized committed effect under current
authority; the authenticated receipt carries that decision from check to commit.
The synchronous gateway, asynchronous consumer, container failover, and
service-integrated transaction are deployment placements and execution stresses.
The integrated implementation stores authoritative state and the effect ledger
together, then verifies the receipt, consumes the confirmation nonce,
deduplicates the trial ID, and inserts the effect in one transaction. Separate
SQLite and PostgreSQL realizations match on same-key discrete outcomes but are
not pooled.

The schedule matrix supports gateway decision consistency and trial-ID
idempotence under delayed, duplicated, concurrent, retried, and reordered
byte-identical requests. The separate 600-row queue matrix adds post-enqueue
invalidation, 300 broker-restart observations, and 120 at-least-once
redeliveries; its two profiles repeat the same 150 scenarios and are not pooled.
The separate 600-row Docker failover matrix adds four shared fault epochs: each
150-row cell is a scenario matrix under one fault, not 150 independent
partition/crash events. It establishes consumer-path disconnect/crash recovery,
not production-broker compatibility, broker-storage partition tolerance, or
replicated consensus. The separate 540-row matrix closes the local
verifier--commit gap: 80 post-verification mutation requests are serialized
after effect commit, and pre-transaction invalidations are blocked. This
establishes service-local transaction atomicity on both tested backends, not
active-channel integrity, WAN prevalence, cross-database distributed
transactions, or production capacity. PostgreSQL uses a longer observation hold,
so backend latencies are not compared.

## Statistical and evidence consistency

- The discovery inventory is labeled configuration-level evidence rather than
  an independent ASR estimate.
- Native instance outcomes are separated from template-clustered inference.
- GPT-5.4 and GPT-5.6-sol are labeled post-hoc coverage and are not pooled with
  the primary aliases.
- Typed replay and composed-action experiments are mechanism stresses, not
  live proposal-rate estimates.
- The same 100 invalidation scenarios recur across five execution schedules;
  schedule-specific results are not pooled as an independent `n=500`.
- The queue profiles repeat the same 150 scenarios and are not pooled as an
  independent `n=300`; the broker is a controlled reference, not a production
  messaging-system claim.
- The Docker failover profiles likewise repeat the 150 scenarios, and each
  policy/profile cell shares one fault epoch; the 600 rows are not 600
  independent infrastructure faults.
- PAuth/PCAS adaptations tie IACG on supplied-effect authorization. The claimed
  distinction is commit-time survival after invalidation, not a relabeled
  method-level win.
- Remote and loopback latency results are bounded to their measured deployment;
  they are not interpreted as WAN overhead or production throughput.

## Outcome

No unresolved terminology conflict, symbol mismatch, evidence-layer pooling,
or section-order contradiction remains. The most consequential narrative
correction is separating the injection vector from the authorization failure,
and separating effect-level enforcement from the deployment stresses used to
evaluate it.

The final closeout adds a compact failure taxonomy, a concrete `t1`
authorization--`t2` change--`t3` commit example, and a published-design
capability table for PAuth/FORGE/IACG. The taxonomy makes the core novelty
explicit: tool misuse checks selection, argument misuse checks a proposed call,
and authorization-boundary escalation checks the committed effect against
current authority. Network conditions remain deployment stresses rather than
the claimed contribution.

The post-edit regression passes 110/110 unit tests, 1,004/1,004 schema files,
75/75 data-derived claim records, 9/9 reviewer-response items, and 17/17
PDF/source submission checks. The combined PDF/source/artifact audit passes
20/20 checks. The final 10-page PDF has a 178-word abstract and SHA-256
`7ab44eac78651996eb9309f6dc2991ce8e5e9d0aaff2a151ef95ae3f3dfcb7f0`.
Because these reports are included in the archive, its non-self-referential
SHA-256 is recorded outside the archive in
`output/infocom_submission_audit.json` after construction.
