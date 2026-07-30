# Multiprocess commit experiment synchronization amendment (2026-07-18)

## Second invalid attempt

The fresh-database retry with a 30 ms mutation hold was rejected by the same
timing-integrity gate before JSONL or derived CSV output. Increasing the hold
did not fix the ordering because releasing two client threads together does not
guarantee that the authorization service receives and applies mutation before
the separate gateway process receives commit.

## Synchronization correction

Before another complete-matrix run, the orchestration is changed to expose a
read-only `mutation-status` route. The commit client waits until the
authorization process reports that mutation is applied, then waits the frozen
2 ms commit delay before contacting the gateway. The mutation handler continues
to hold the authorization-state lock for 30 ms. Receipt-bound state retrieval
therefore crosses the HTTP boundary and observes the updated state after the
hold, while stale pre-action policies can commit during the invalidation
window.

The status route does not alter state, issue authorization, choose a policy
decision, or provide oracle labels. All scenarios, policies, denominators,
service delays, duplicate-delivery schedule, and integrity gates remain
unchanged. The third attempt must restart from a fresh database and report all
prior invalid attempts.

Post-correction runner SHA-256 before the third attempt:
`f703907a18fc0db0fc54a87a9cf637064adc67296b29ad5e15cc32913d8c2cbd`.
