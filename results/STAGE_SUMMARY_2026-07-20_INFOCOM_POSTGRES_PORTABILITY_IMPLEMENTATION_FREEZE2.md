# INFOCOM PostgreSQL portability implementation freeze 2 (2026-07-20)

## Amendment readiness

This freeze supersedes only the two hashes changed by the dated 30 ms timing
amendment. Seven focused unit tests pass. A real HTTP/child-process/PostgreSQL
preflight on the previously failed synthetic scenario observes all five gates:
verification active, mutation requested after verification, mutation blocked
on the row lock, effect linearized before mutation, and exactly one effect row.
The preflight container/schema were removed and no formal CSV exists.

## Frozen hashes for the retry

| File | SHA-256 |
|---|---|
| `runner/run_service_integrated_commit.py` | `4268c76a7a8a12ee1e0a623025e9ebbcc09b6e48b71c5171d66e8d1cce4eacc3` |
| `runner/run_postgres_integrated_commit.py` | `4badbe7447845fe532b0a9a99e6e236a2999caf0e6ad7b626bf723420bdd43f1` |
| `tests/postgres_http_preflight.py` | `39003469a5d63b5c079ca548ea59009d5e35f2c39ce195442411b9b00b50ef6b` |
| `runner/postgres_integrated_commit.py` | `533157c70bd8cb3783ef26809192197b7c250b8613ea2d4aca30f993f870012d` |
| `analysis/audit_postgres_integrated_commit.py` | `b8051cd34d27568fb46b02e1bcf7dcca982cf686f64257975d904f75a68a8079` |
| `scripts/run_postgres_integrated_commit.sh` | `c06563170deb5124b98b899c562757fea77e37ea04dc209593d1a1e70b77ff52` |
| `scenarios/commit-race-heldout/MANIFEST.csv` | `2fcdadacae83242b61754567ba00c61c79a5e4738c676009fac0985f0203b028` |

All unchanged hashes and environment fields from the first implementation
freeze remain binding. The PostgreSQL condition now passes an explicit 30 ms
hold to the shared helper; the helper default and existing SQLite matrix remain
10 ms.

The retry must invoke `bash scripts/run_postgres_integrated_commit.sh` without
`--overwrite` or resume options. It is a wholly fresh 540-row attempt and may
publish results only after the complete in-memory validation succeeds.
