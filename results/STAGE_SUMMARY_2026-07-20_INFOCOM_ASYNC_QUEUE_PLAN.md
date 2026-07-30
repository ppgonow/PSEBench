# INFOCOM asynchronous queue commit plan (2026-07-20)

## Objective

Test the network-specific interval created when an agent gateway authorizes and
enqueues an effect, but an independently running consumer reaches the effect
service only after authorization state changes. The experiment asks whether a
cached enqueue-time allow remains stale across asynchronous delivery and
whether transaction-bound receipt verification blocks it while preserving
controls and at-least-once redelivery idempotence.

This is a new supporting matrix. It does not modify, replace, selectively rerun,
or pool the existing 1,500-row synchronous schedule matrix or either 540-row
service-integrated backend matrix.

## Frozen inputs and roles

- scenarios: the existing `scenarios/commit-race-heldout/` set containing 100
  invalidations and 50 stable controls;
- policies: `check-once` and `receipt-bound`;
- profiles: `steady-consumer` and `broker-restart`;
- roles: producer/runner, a loopback-only durable broker process, and a
  loopback-only service-integrated effect process;
- storage: separate temporary SQLite files for broker state and effect state;
- authentication: a fresh in-memory 32-byte HMAC key for the run;
- duplicate schedule: every fifth scenario loses its first acknowledgement,
  is released to the queue, and is delivered a second time.

The durable broker is a minimal auditable reference, not a RabbitMQ, Redis,
Kafka, or production queue implementation. It exposes enqueue, claim, release,
acknowledge, status, and health operations on loopback HTTP. A test-only
substitute operation may replace the payload of an unclaimed message exactly
once for the `effect-substitution` attack family; it is rejected after any
delivery. This supplies the frozen post-enqueue payload mutation while the
receipt remains unchanged.

## Matrix and causal gates

Each profile/policy cell contains the same 150 scenario IDs, giving 600 unique
profile/policy/scenario observations. Same IDs repeated across profiles are
schedule replications and are not independent samples.

For every attack row, the producer must observe this logical happens-before
chain without comparing service clocks:

1. broker enqueue response received;
2. authorization mutation response received (and, for effect substitution,
   broker payload-substitution response received);
3. first broker claim response received;
4. effect-service decision received.

For `broker-restart`, the original broker process must terminate after all 150
enqueue/mutation steps, a new broker process must open the same temporary queue
database, and all 150 messages must then be claimable in FIFO enqueue order.

## Frozen outcome gates

- 600 rows and 600 unique profile/policy/scenario keys;
- 400 attack rows and 200 controls;
- `check-once`: 100/100 stale commits per profile;
- `receipt-bound`: 0/100 stale commits per profile;
- all four cells preserve 50/50 controls;
- 400/400 attack rows pass enqueue-before-mutation and
  mutation-before-delivery gates;
- 300/300 `broker-restart` rows are delivered after a broker PID change;
- 120 duplicate rows yield 720 delivery/commit attempts total;
- every row is acknowledged exactly once and leaves no queued/inflight item;
- every allowed row has exactly one effect; every blocked row has zero;
- every duplicate allowed row has two attempts but one idempotent ledger effect;
- broker and effect roles are distinct from the producer for every row;
- an independent daemon-free audit reconstructs summary and integrity CSVs
  byte-for-byte from the detail CSV.

Any infrastructure, identity, completeness, causality, FIFO, redelivery,
idempotence, or cleanup failure invalidates the complete attempt. Formal output
files are written only after all rows and aggregate gates pass.

## Claim boundary

Passing the matrix establishes correctness for a controlled loopback,
database-backed at-least-once queue reference. It does not establish production
broker compatibility, queue partition tolerance, cross-database atomicity,
multi-tenant isolation, WAN prevalence, or independently administered services.
