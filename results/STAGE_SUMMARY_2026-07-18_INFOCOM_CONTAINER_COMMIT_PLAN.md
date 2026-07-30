# Container-isolated commit-bound replication plan (2026-07-18)

## Registration and claim boundary

This protocol is locally specified before implementation hashes and complete
matrix outcomes are observed. It is a same-host Docker replication with three
isolated containers and network namespaces. It is not a multi-physical-host,
cloud-provider, independently administered production-service, or distributed
transaction experiment.

The result may enter the paper only if the complete matrix and public audit pass
and only as supporting network-isolation evidence. It cannot replace or pool
with the completed three-process experiment.

## Fixed topology

- One user-defined Docker bridge network.
- `authorization`: mutable authority/effect state and receipt issuer.
- `gateway`: proposal-time or receipt-bound commit decision.
- `effect`: idempotent SQLite-backed external-effect ledger.
- Each role must run in a distinct container, network namespace, and IP address.
- Host access is limited to loopback-published test ports.
- No production account, third-party service, or external user is contacted.

## Fixed matrix

- Scenario corpus: existing 150-scenario commit-race manifest.
- Composition: 100 invalidations and 50 stable controls.
- Families: effect substitution, authorization revocation, principal switch,
  confirmation replay, and lease expiry.
- Policies: `check-once`, `PAuth-style/pre-action`,
  `PCAS-style/pre-action`, and `receipt-bound`.
- Total: 600 unique policy/scenario observations.
- PAuth-style and PCAS-style are typed pre-action adaptations, not official
  implementations. PCAS-style is the internal policy-compilation label.

## Fixed orchestration

- Mutation-active observation occurs through the authorization container before
  the host client sends each attack request to the gateway container.
- Mutation hold: 30 ms; post-observation commit delay: 2 ms.
- Authorization-state response delay: 0.5 ms.
- Effect-service response delay: 0.5 ms.
- Every fifth scenario schedules duplicate downstream delivery.
- The effect service must reduce duplicate attempts to one ledger commit.

## Reportability gates

- Exactly 600 unique policy/scenario rows and 150 IDs per policy.
- Exactly three distinct container-ID hashes, network-namespace hashes, and IPs.
- All services use the same non-host user-defined bridge network.
- All 400 attack-policy rows observe active mutation immediately before commit.
- Allowed rows have one ledger entry; blocked rows have zero.
- Scheduled allowed duplicates have two attempts and one ledger entry.
- Same-ID exact McNemar tests and Wilson intervals reproduce from public CSVs.
- Raw Docker IDs, ephemeral HMAC key, SQLite database, and raw JSONL remain local.

An infrastructure failure invalidates the complete attempt. No failed row may
be dropped, replaced, or counted as a new sample; amendments must be recorded
before a fresh retry.

## Network amendment and frozen implementation

The Docker Desktop compatibility amendment is recorded in
`results/STAGE_SUMMARY_2026-07-18_INFOCOM_CONTAINER_NETWORK_AMENDMENT.md`.
It preserves the one user-defined bridge, distinct namespaces, and loopback
publication while explicitly setting `network_internal=0`; the result is not
reported as internal-network or production-egress evidence.

The macOS Bash compatibility amendment is recorded in
`results/STAGE_SUMMARY_2026-07-18_INFOCOM_CONTAINER_SCRIPT_AMENDMENT.md`.

The implementation was frozen after the health/topology preflight with these
SHA-256 digests:

| File | SHA-256 |
|---|---|
| `runner/container_commit_service.py` | `4a42ac72a29a9dc9968273b5b8b43c5b43c263a6112cfe16009caa0126e527e3` |
| `runner/run_container_commit_race.py` | `96038d30b387a1a5732a4d703b976b9e09899857458a27877f114afc3e2cc994` |
| `analysis/audit_container_commit_race.py` | `e001ca9dbf264c25fc027a8cf0ccf9c4c571bb06a3f6bcb16acc2a452be29204` |
| `tests/test_container_commit_race.py` | `6c3e00c09ef0cb55ffb3ceec22d2a616ba32b615dcd9d3b3e83c960da63f2169` |
| `container/commit-race/Dockerfile` | `26ea76698e92ceae1a4f9db0fa44da46f27a0beccfb05e4ffdca38b7b90067f9` |
| `container/commit-race/compose.yaml` | `7efc6da3d01a95a22b83ca63114435c8871641b70d359bc874f5e0fc3a86b414` |
| `scripts/run_container_commit_race.sh` | `fe098167062927560f4dfdc7050feddca19b2bf3daf7080d5e3b195e109c9c2c` |
| `.dockerignore` | `b154a8dfe89a8d225de2eae5f6fe890d5347602d15cdf7f886cbffc5c92a7693` |

The base image is pinned to
`python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de`.
