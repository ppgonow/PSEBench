# INFOCOM commit-gateway load plan (2026-07-19)

## Status and question

This protocol is frozen before the first reportable load request. It measures
the stable authorized path through the existing three-process HTTP
authorization, gateway, and SQLite effect services. It asks how receipt-bound
revalidation changes throughput and tail latency under concurrent benign load;
it does not estimate attack prevalence or production capacity.

## Frozen matrix

- Policies: `check-once` and `receipt-bound`.
- Concurrent clients: 1, 8, and 32.
- Repeats: three per policy/concurrency condition.
- Measured requests: 200 per repeat, 3,600 total.
- Warm-up: 10 requests per condition/repeat, 180 total, excluded from output.
- Authorization-state and effect-service delays: 0.5 ms each.
- Traffic: stable authorized effects only; no mutation and no duplicate delivery.
- Order: concurrency increases 1, 8, 32; policy order reverses on even repeats.
- Outputs: per-request client, gateway, authorization-query, and service-call
  latency; per-condition median throughput and pooled p50/p95/p99 latency.

Every measured request must commit exactly once, make exactly one delivery
attempt, and leave exactly one SQLite ledger row. A missing request, exception,
failed commit, duplicate ledger row, or protocol/configuration change invalidates
the complete run. Failed rows may not be dropped or selectively rerun.

## Claim boundary

The run is a controlled single-host three-process HTTP benchmark. It includes
HTTP connection setup and a serialized SQLite effect service. It does not claim
WAN, multi-host, production database, TLS, provider, or distributed-transaction
performance. Results are descriptive system measurements, not independent
security samples.

## Pre-execution hashes

| Artifact | SHA-256 |
| --- | --- |
| Load runner | `7fab3e50fa2071f789e76825fc08641f1f5913ce23040afc5537b8674227683d` |
| Independent auditor | `7e4a20968ac8a5df984b7cfa266f3ff09c3c96e320ba4e9aba30a74075be4596` |
| Load tests | `53a3a64bf82c412ea545fef3608c92171e8bfae8f159690fbce60ca160b7f27f` |
| Three-process service implementation | `09c01d2bb822061db970291b65403558bbcee542540cc57eddda3848e226dfcb` |
| Commit-race manifest | `2fcdadacae83242b61754567ba00c61c79a5e4738c676009fac0985f0203b028` |

## Reportable command

```bash
python3 runner/benchmark_commit_gateway_load.py
```

The independent post-run audit must regenerate a byte-identical summary from
the released detail CSV before any result enters the paper.
