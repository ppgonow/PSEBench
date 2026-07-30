# INFOCOM commit-gateway load result (2026-07-19)

## Reportable run

After the two invalid short-connection attempts recorded in the amendments, a
non-reportable concurrency-32 pilot completed 50 measured requests per policy.
The formal matrix then restarted from its first condition and completed in one
uninterrupted run. It contains:

- two policies: `check-once` and `receipt-bound`;
- concurrency 1, 8, and 32;
- three repeats and 200 measured requests per policy/level/repeat;
- 10 unreported warm-up requests per condition/repeat;
- fixed 0.5 ms authorization-state and effect-service delays;
- 3,600 measured requests and 3,600 unique measured keys.

The public detail CSV contains only measured requests. The local SQLite ledger
also contains the 180 warm-ups, giving 3,780 unique commits and 3,780 delivery
attempts. Every measured request committed exactly once with one delivery and
one ledger row.

## Results

| Policy | Concurrency | Median throughput (req/s) | Client p50 (ms) | Client p95 (ms) | Client p99 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| check-once | 1 | 614.970 | 1.588 | 1.834 | 2.020 |
| receipt-bound | 1 | 373.406 | 2.654 | 3.063 | 4.698 |
| check-once | 8 | 893.892 | 8.833 | 13.085 | 14.136 |
| receipt-bound | 8 | 911.436 | 8.722 | 9.554 | 10.955 |
| check-once | 32 | 888.581 | 35.374 | 36.422 | 36.737 |
| receipt-bound | 32 | 890.031 | 35.188 | 37.712 | 38.017 |

At concurrency one, commit-time revalidation reduces throughput and increases
latency because it adds an authorization-state round trip. At concurrency 8
and 32, both policies saturate the serialized SQLite effect ledger near 0.9k
requests/s; receipt binding does not reduce saturated throughput in this local
reference implementation. The concurrency-32 p99 includes queueing. These
measurements are a loopback process/path stress test, not WAN, production,
multi-tenant, or distributed-database capacity evidence.

## Independent audit

`analysis/audit_commit_gateway_load.py` reconstructs the six summary rows from
the detail CSV, requires the frozen 3,600-key matrix, and rejects any request
without exactly one commit, delivery, and ledger row. Its output is
byte-identical to the released summary.

## Frozen hashes

| File | SHA-256 |
| --- | --- |
| `runner/benchmark_commit_gateway_load.py` | `c5f67cc41d0b3dc15a2e5564ea63c921dc59ea4be804ba3bdd7556ff04559f9e` |
| `runner/run_multiprocess_commit_race.py` | `d7101775b113099c30a5664bff9973e340c31da3a1346258d0ffc48d7a62668f` |
| `analysis/audit_commit_gateway_load.py` | `7e4a20968ac8a5df984b7cfa266f3ff09c3c96e320ba4e9aba30a74075be4596` |
| `tests/test_commit_gateway_load.py` | `ccb98b3c87b469e219a896ab2125911d8819ac3779ff3905c093a81301229df6` |
| `analysis/commit_gateway_load_detail.csv` | `7b8716e5c6f76fbcb7dc902b59c028c85b3c4f7458b6b8fb51da125aba200eda` |
| `analysis/commit_gateway_load_summary.csv` | `5a152e4c703e23eae37f4a03ea467b0c566a44ca1d9c33282b0d648be514d33a` |

The local SQLite file was deleted after audit and is not used by the
daemon-free public audit.
