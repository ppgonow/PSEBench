# INFOCOM PostgreSQL portability failed formal attempt (2026-07-20)

## Disposition

The first formal PostgreSQL portability attempt is invalid and excluded in its
entirety. It must not be selected, repaired row-by-row, pooled, or described as
the reportable matrix.

## Failure

The runner completed request execution but stopped at the pre-publication
validation gate. One synthetic critical-window service-atomic row
(`RACE-authorization-revocation-attack-020`) had:

- verifier gate observed;
- mutation requested after verification;
- effect commit linearized before mutation;
- exactly one idempotent effect;
- but `mutation_deferred_at_gate=0` when the status observer sampled telemetry.

The frozen 10 ms post-verification hold was insufficient for the PostgreSQL
connection/HTTP status observer to sample the blocked row-lock interval on this
attempt. This is a causal-gate observation failure even though the recorded
linearization order was effect before mutation.

## Publication and cleanup gates

No `analysis/postgres_integrated_commit_*.csv` file was written because the
runner validates the full in-memory matrix before publishing outputs. The
disposable container, schemas, password, database, HMAC key, and loopback port
were removed. A post-failure check found no experiment container and no formal
PostgreSQL CSV.

Any retry requires a dated amendment and a wholly fresh 540-row run.
