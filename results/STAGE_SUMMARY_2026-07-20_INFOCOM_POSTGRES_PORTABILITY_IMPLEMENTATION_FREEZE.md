# INFOCOM PostgreSQL portability implementation freeze (2026-07-20)

## Readiness outcome

The implementation is frozen for one complete 540-row PostgreSQL portability
matrix. Static compilation, shell syntax, and seven focused unit tests pass. A
separate disposable PostgreSQL preflight passes 3/3 integration tests covering
pre-transaction split/atomic divergence, post-verification row-lock
serialization, and nonce/idempotent duplicate handling. The preflight produced
no paper CSV and its container/schema were removed.

## Frozen environment

- PostgreSQL image:
  `postgres@sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193`
- Psycopg: `3.3.4`
- Docker client/server: `27.3.1` / `27.3.1`
- Scenario manifest SHA-256:
  `2fcdadacae83242b61754567ba00c61c79a5e4738c676009fac0985f0203b028`

## Frozen implementation hashes

| File | SHA-256 |
|---|---|
| `requirements.txt` | `5c75f8e2faa3485ac121defddf395a40c18af3a91e601d2d3e8ad3cf8b023f29` |
| `runner/postgres_integrated_commit.py` | `533157c70bd8cb3783ef26809192197b7c250b8613ea2d4aca30f993f870012d` |
| `runner/run_postgres_integrated_commit.py` | `4158e62bcc177c36c19b49237000bfe7ac99450d6731d77360fb5be36438da16` |
| `analysis/audit_postgres_integrated_commit.py` | `b8051cd34d27568fb46b02e1bcf7dcca982cf686f64257975d904f75a68a8079` |
| `tests/test_postgres_guardrails.py` | `8fb2b160f04f1f58d1cb6f45d4fd1baa1ebb5e48db49461b92ae99e9cd44a697` |
| `tests/postgres_integration.py` | `0e16d7b0ce227174ffaf259f012bbbe90c20f3a9017c3000de95eb83449946d7` |
| `scripts/run_postgres_integrated_commit.sh` | `c06563170deb5124b98b899c562757fea77e37ea04dc209593d1a1e70b77ff52` |

## Formal run rule

The formal invocation is exactly:

```bash
bash scripts/run_postgres_integrated_commit.sh
```

The runner refuses pre-existing outputs. It creates one disposable,
loopback-only PostgreSQL container, uses four fresh condition schemas, validates
all 540 rows before publishing any CSV, then stops and removes the container.
No `--overwrite`, resume, row replacement, selective rerun, or cross-backend
pooling is allowed.

Any code, scenario, image, isolation, timing, or validation change after this
record requires a dated amendment and a wholly fresh run. Infrastructure
failure invalidates the entire attempt and must be documented before retry.
