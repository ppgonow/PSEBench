# INFOCOM PostgreSQL portability timing amendment (2026-07-20)

## Reason

The first formal attempt failed only the critical-window dwell observation:
one row linearized effect before mutation, but the 10 ms transaction hold ended
before the independent status request sampled `mutation_lock_acquired_ns=None`.
The complete attempt was discarded before any CSV was written.

## Single permitted change

For the PostgreSQL portability condition only, increase the atomic
post-verification hold from 10 ms to 30 ms. This hold creates an observable
interval after receipt verification while the PostgreSQL row lock remains held.
It does not change the receipt, authorization state, effect, transaction
contents, lock acquisition order, policy decision, duplicate schedule, or
linearization criterion.

The existing SQLite matrix and its runner retain the original 10 ms hold. The
shared `run_case` helper will accept an explicit hold parameter with a 10 ms
default; the PostgreSQL runner supplies 30 ms. All other plan and implementation
freeze conditions remain unchanged.

## Retry rule

After focused tests and a second implementation-freeze hash record, rerun all
540 rows from a fresh disposable container and fresh schemas. The retry remains
invalid if any one of the 80 critical atomic rows lacks the verifier gate,
post-verification mutation request, observed blocked-lock dwell, or effect-before-
mutation linearization. No output from the failed attempt may be reused.
