# INFOCOM PostgreSQL portability implementation freeze 3 (2026-07-20)

## Host-readiness outcome

The amended launch path passes shell/static checks and a disposable
infrastructure-only preflight: PostgreSQL is ready inside the container and a
host-side Psycopg `SELECT 1` succeeds through the exact randomly assigned
`127.0.0.1` DSN. No scenario or formal output ran. The container and credential
were removed.

## Frozen retry hashes

The only hash changed since freeze 2 is the launch script:

| File | SHA-256 |
|---|---|
| `scripts/run_postgres_integrated_commit.sh` | `1952492143445096639fbb4c912ed5955dd053f8e98533642e810efd52d68955` |
| `runner/run_service_integrated_commit.py` | `4268c76a7a8a12ee1e0a623025e9ebbcc09b6e48b71c5171d66e8d1cce4eacc3` |
| `runner/run_postgres_integrated_commit.py` | `4badbe7447845fe532b0a9a99e6e236a2999caf0e6ad7b626bf723420bdd43f1` |
| `runner/postgres_integrated_commit.py` | `533157c70bd8cb3783ef26809192197b7c250b8613ea2d4aca30f993f870012d` |
| `analysis/audit_postgres_integrated_commit.py` | `b8051cd34d27568fb46b02e1bcf7dcca982cf686f64257975d904f75a68a8079` |
| `tests/postgres_http_preflight.py` | `39003469a5d63b5c079ca548ea59009d5e35f2c39ce195442411b9b00b50ef6b` |
| `scenarios/commit-race-heldout/MANIFEST.csv` | `2fcdadacae83242b61754567ba00c61c79a5e4738c676009fac0985f0203b028` |

All protocol and matrix conditions from freeze 2 remain binding. The next
attempt starts a fresh container and must complete all 540 rows before writing
any CSV.
