# Three-host commit-bound replication plan (2026-07-18)

## Registration and claim boundary

This protocol is locally specified before remote hosts are configured and
before any matrix outcome is observed. It requires three distinct Linux hosts
or cloud VMs with distinct machine and boot identities. Containers, VMs, or
network namespaces sharing the current macOS/Docker host do not satisfy this
protocol.

The result may enter the paper only after the complete matrix and a daemon-free
public audit pass. It is a three-host service experiment, not evidence of
independently administered providers, production traffic, distributed
transactions, or TLS correctness unless those properties are separately
established.

## Fixed topology

- `authorization`: mutable authorization/effect state and receipt issuer on
  host A.
- `gateway`: stale or receipt-bound commit decision on host B.
- `effect`: idempotent SQLite external-effect ledger on host C.
- The three roles must have distinct SHA-256 hashes of `/etc/machine-id`,
  `/proc/sys/kernel/random/boot_id`, SSH target, service endpoint host, and
  hostname.
- Host B must reach the private authorization and effect endpoints over TCP.
- The experiment client must reach authorization and gateway endpoints; effect
  access is needed only for health/topology preflight.
- Firewall or security-group rules must restrict service ports to the three
  experiment hosts and client address. No public account, third-party service,
  or external user is contacted.
- Raw hostnames, addresses, SSH targets, machine IDs, boot IDs, logs, key
  material, and SQLite files remain local. Public topology data contains only
  hashes and non-identifying capability fields.

## Fixed matrix

- Existing 150-scenario commit-race manifest: 100 invalidations and 50 stable
  controls.
- Five families: effect substitution, authorization revocation, principal
  switch, confirmation replay, and lease expiry.
- Four policies: `check-once`, `PAuth-style/pre-action`,
  `PCAS-style/pre-action`, and `receipt-bound`.
- Total: 600 unique policy/scenario observations.
- PAuth-style and PCAS-style remain typed adaptations, not official system
  implementations.

## Fixed orchestration

- The client first receives an authorization-host acknowledgment that mutation
  is applied and still active, then sends the gateway commit request. This
  logical happens-before relation is the causal gate; timestamps from different
  hosts are never directly compared.
- Mutation hold: 1,000 ms; post-observation commit delay: 10 ms.
- Authorization-state and effect-service response delays: 0.5 ms each.
- Every fifth scenario schedules duplicate downstream delivery; the effect host
  must retain one ledger row.
- The HMAC key is generated ephemerally, copied only to authorization and
  gateway hosts with owner-only permissions, never printed, and removed during
  cleanup.

## Readiness gates

- Passwordless `BatchMode=yes` SSH succeeds for all three configured aliases.
- Each host provides Python 3.10 or newer and the frozen Python dependency set.
- Host probes produce three distinct machine-ID, boot-ID, endpoint-host, SSH
  target, and hostname hashes.
- Authorization/gateway/effect health endpoints return the expected logical
  role identities.
- Gateway-to-authorization and gateway-to-effect connectivity passes before a
  scenario request is sent.
- Remote working directories and ledgers are fresh for the attempt.

## Reportability gates

- Exactly 600 rows, 600 unique policy/scenario keys, and 150 IDs per policy.
- All 400 attack-policy rows pass the mutation-active happens-before gate.
- Allowed rows have one ledger entry; blocked rows have zero.
- Scheduled allowed duplicates have two attempts and one ledger entry.
- Same-ID McNemar tests, Wilson intervals, latency summaries, topology hashes,
  and integrity totals reproduce from public CSVs without SSH access.
- Results are reported separately from the process and Docker replications and
  are not pooled as independent scenarios.

An infrastructure failure invalidates the full attempt. No failed row may be
dropped or replaced. The cause and any protocol amendment must be recorded
before a fresh retry.
