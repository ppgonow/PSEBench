# INFOCOM Review-Response Evidence Audit (2026-07-15)

## Purpose

This audit maps the two ACSAC reviews to the current INFOCOM manuscript and
released evidence. It does not treat every added scenario as equivalent to a
live end-to-end run. Items remain `partial` where the requested external or
model-driven evidence has not been obtained.

## Mapping

| review concern | current status | direct response | remaining boundary |
|---|---|---|---|
| Small defense conditions | substantially addressed | 100 held-out attacks, 150 frozen authorization cases, 120 non-cron utility cases, 60 multi-tool chains, Wilson and paired tests | primary live matched slices remain small |
| Missing uncertainty | addressed | run inventory and unique scenarios are separated; fixed-condition unique-scenario or semantic-template rates use Wilson intervals and paired designs use exact McNemar | small paired cells still have wide intervals |
| Shared guard/oracle vocabulary | substantially addressed | runtime prompt inference is separate from typed ground truth; proposed-effect replay avoids cue labels; rule hashes are frozen before fresh generation | deterministic inference still sends novel durable wording to confirmation |
| No adaptive attacker | substantially addressed | 100 cue-independent effect attacks plus frozen covered/novel/ambiguous wording conditions | contaminated confirmation is pending model execution |
| Missing Task Shield/PFI | partially addressed | both are cited and typed adaptations are evaluated | no official Task Shield run is claimed |
| Missing artifact | partially addressed | independently verified anonymous ZIP and reproduction manifest exist | an account-neutral hosted URL is still required |
| Novelty unclear | addressed | related work now separates LLM task contribution, data-flow privilege, stored injection, and committed-effect escalation | IACG remains a narrow reference monitor |
| Unrealistic workflows | substantially addressed | sandboxed non-cron artifacts, two-tool action sequences, authorization utility, and overlapping localhost HTTP commit transitions with a SQLite ledger | no broad live multi-turn or distributed transaction evaluation |
| Decision-only cross-model tests | substantially addressed | schema-neutral native shared-proposal forks cover 320 instances across four author-verified requested aliases, with SQLite-backed effects and template-cluster analysis | synthetic scenarios and one compatible endpoint do not establish broad provider-independent robustness |

## Closest-Work Feasibility Check

The Task Shield paper and ACL Anthology page expose no official source-code
repository. The paper states that both task-instruction extraction and
`ContributesTo` scoring use an LLM and that the same GPT-4o-family model is used
as the shield. A credential-free official run is therefore not available.
PSEBench keeps its baseline named `TaskShield-style` and explicitly labels it a
typed adaptation; changing that label to “official Task Shield” would be
methodologically incorrect.

The manuscript now also distinguishes Xie et al. (arXiv:2606.04425): that work
studies adversarial content stored in agent state and influencing later
sessions, whereas PSE labels persistence, destination, or scope enlargement in
the external effect of an already authorized action. Either threat can coexist,
but they are different evaluation units.

## Automated Check

`analysis/reviewer_response_audit.py` verifies all nine evidence bundles and,
when the ignored paper source is locally present, checks the corresponding
boundary language in the manuscript. The generated mapping is
`analysis/reviewer_response_audit.csv` and is included in the no-credential
sanity entry point.

## Remaining Gates

1. Host the final anonymous ZIP through an account-neutral reviewer channel.
2. Do not interpret the zero-ASR native matrix as action-policy efficacy; the
   shared provenance prompt produces no unsafe proposal under permissive
   action-layer execution, and only 282/288 traces invoke sender confirmation.
3. Do not claim official Task Shield, broad live multi-turn coverage, or real
   distributed-race validation unless those experiments are actually run.
