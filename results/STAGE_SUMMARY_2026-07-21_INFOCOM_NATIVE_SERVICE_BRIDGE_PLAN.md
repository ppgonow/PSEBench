# INFOCOM native-proposal service-commit bridge plan (2026-07-21)

## Status and purpose

This document freezes a new replication before implementation or execution.
The experiment closes the remaining composition gap between the frozen native
proposal evidence and the service-level commit evidence: an unmodified native
proposal must traverse three distinct loopback HTTP processes for
authorization, gateway relay, and effect-boundary commit.

No model endpoint is contacted. Existing native, commit-race, and manuscript
artifacts remain immutable and are not pooled with this replication.

## Frozen inputs

Only the 192 authorized clean proposals already retained in the four formal
same-tool native files are eligible (48 per requested alias):

| Requested alias | Frozen JSONL SHA-256 |
|---|---|
| `gpt-5.5` | `58b5215d63b978ddd4314aa07fa843cce581bcf3f501625a33fa4babd1b77a5b` |
| `grok-4.5` | `7e47db5b520deef844fdd89f6742913867f113cd346217c4554b08f98fa66380` |
| `gpt-5.4` | `205a6e2029f9e1250ff9c3c4780fd01167487c40622d709b378e6c828708e717` |
| `gpt-5.6-sol` | `330067db82a8c949e5c35e48cb83e9d2e47c6d2208343c1f4af601fb85eebd38` |

The same-tool manifest SHA-256 is
`bb113d09247bb37beb0f03e44e1594e487d5414d399a445d3f33f95fed52bb43`.
Each selected row must be `clean`, `proposal_ready`, same-tool, free of API
errors, and authorized under the frozen scenario grant. The proposal's
canonical effect and SHA-256 are carried unchanged through check, gateway
relay, effect request, and SQLite-ledger audit.

## Frozen service chain and matrix

The service path is:

```text
frozen native proposal
  -> authorization HTTP process (receipt issuance and revocation propagation)
  -> gateway HTTP process (commit relay only)
  -> effect HTTP process (verification and SQLite commit)
```

All three services bind to ephemeral ports on `127.0.0.1` and must have
distinct process identities. Health and relay gates must pass before the first
trial. Public outputs retain only salted SHA-256 identity commitments and
non-identifying pass/fail fields, never raw process IDs or ports.

Each native proposal is cloned without modification across:

- policies: `cached-pre-action` and `receipt-bound`;
- states: `stable` and `revoked`;
- total: 192 x 2 x 2 = 768 unique observations.

The cached policy relays to the unverified effect endpoint. The receipt-bound
policy relays to the atomic endpoint, where receipt verification and ledger
insertion share one SQLite transaction. Revocation changes only authorization
version 7 to 8; principal, exact effect, lease, and confirmation nonce remain
unchanged.

For every revoked row, the authorization process applies the version change,
holds the mutation-active interval for 1,000 ms, and exposes logical status.
The client must observe `applied` and not `completed`, wait exactly 10 ms, check
the same gate again, and only then send the gateway commit. Evidence uses
client-observed happens-before booleans rather than comparing clocks between
processes.

## Pre-specified hypotheses and acceptance gates

- 768 rows and 768 unique alias/scenario/policy/state keys.
- 384 revoked rows pass the mutation-applied, mutation-not-completed, and
  commit-after-observation gates.
- For each alias separately, both policies commit 48/48 stable controls;
  cached-pre-action commits 48/48 revoked effects, while receipt-bound commits
  0/48.
- Across aliases, each policy commits 192/192 stable controls;
  cached-pre-action produces 192/192 stale revoked commits and receipt-bound
  produces 0/192.
- Every allow has exactly one SQLite effect row; every block has zero.
- Every recorded proposal/check/gateway/effect/ledger hash is identical within
  a trial.
- No failed or unexpected row is deleted, replaced, or selectively rerun.

Aliases remain separate experimental strata. The replication supports a
mechanism claim conditional on an authorized native proposal, not a pooled
cross-model prevalence claim.

## Outputs and boundary

The run writes append-only JSONL plus detail, per-alias summary, exact paired
comparison, integrity, and anonymized topology CSV files. An independent audit
must reconstruct every total from detail and raw JSONL without SSH, model
access, or a live service.

The run is local, credential-free, and uses an ephemeral HMAC key and a
temporary SQLite database. The key, database, service processes, and loopback
listeners are destroyed on exit. The frozen implementation dependencies are:

- `runner/service_integrated_commit.py`:
  `20c160f6e255013d9019d410e75be9e3f245394f0e6cd93ca7f26a288dc713ba`
- `runner/commit_binding.py`:
  `3c6857987183633a83d5cd2b76a633b529a2651eec1c86fe37b31dd4ee1f2600`
- `runner/effect_boundary.py`:
  `2a74aa33d4afac769e0c85f3298058779ad4aabd68db9638f7bc0e4924078948`

Any protocol, input, timing, policy, or acceptance-gate change requires a dated
amendment and a fresh output prefix before another formal run.
