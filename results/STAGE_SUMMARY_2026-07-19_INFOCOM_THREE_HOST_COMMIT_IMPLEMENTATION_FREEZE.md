# Three-remote-instance implementation freeze (2026-07-19)

## Pre-outcome status

This record was created after two zero-scenario remote readiness passes and
before any `/check`, `/mutate`, `/state`, `/commit`, or matrix request was sent
for the reportable attempt. Both readiness passes verified the amended remote
identity constraints, loopback service health, client SSH forwarding, and the
gateway-to-authorization/effect SSH relay. Their remote directories and service
processes were then independently counted at zero.

The complete local suite passed 87/87 tests immediately before this freeze. No
remote matrix output existed. The next run is all-or-nothing: 600 rows from one
fresh deployment, or no reportable result.

## Frozen content hashes

- Protocol amendment:
  `c04b1b63e65a90d8601b8f92c76d839d75405d368e4c2b6c2157eed5b7b16528`
- Remote service:
  `6d491f2a252f94b560e9812d1170d2a13070ce131a093df5a4a90b1d6d250e92`
- SSH orchestrator and matrix runner:
  `68f7a4351683e44ff984fbcdc8b8d86c79ac66948522e83ce355e38f1d67c7e3`
- Daemon-free public audit:
  `7d88e8f0a61a411b6394f52528d21c3425d68a2d94beb2388f51c5c97d63b52f`
- Remote experiment tests:
  `db52dd5f88938b17df74ffeb74d448296e77dc8e7ddea7ce01fbdc64950c165d`
- Reproduction entry point:
  `9e552a8bcad32ab38105b4a33aedb2ee1bf515d988a2d644637d36eaa9c7da2b`
- Frozen scenario directory digest (sorted per-file SHA-256 stream):
  `e1e1752b882ccdcbfc7a7dbb04ed0bee3c10c1140dc5bca8367288a7dda03d2d`
- Scenario manifest:
  `2fcdadacae83242b61754567ba00c61c79a5e4738c676009fac0985f0203b028`
- Commit-binding implementation registered by the scenario snapshot:
  `c605a40ce0512ab7d518573ff91da95a0822f6276e4a6ae5803e6074830f9cd5`

The formal run must use the fixed 10 ms post-observation delay, 1,000 ms
mutation hold, and 0.5 ms authorization/effect service delays. A content change
or failed attempt requires a dated amendment before any retry.
