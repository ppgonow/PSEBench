# INFOCOM Docker queue failover plan (2026-07-20)

## Objective and claim boundary

Test receipt-bound commit when an at-least-once queued effect is claimed by one
consumer, that consumer loses the effect-service network path or is killed
after commit but before acknowledgement, and a second consumer takes over.

No Redis, RabbitMQ, NATS, Kafka, or compatible image/runtime is available in the
authorized offline environment. The experiment therefore containerizes the
auditable PSEBench broker semantics rather than claiming a production broker.
It supports Docker-level partition/crash and consumer-failover evidence only.

## Frozen matrix

- profiles: `partition-before-commit` and `crash-after-commit`;
- policies: `check-once` and `receipt-bound`;
- scenarios: the same frozen 100 invalidations and 50 controls per cell;
- total: 600 unique profile/policy/scenario rows;
- roles per cell: broker, effect service, consumer A, and consumer B;
- image: local `python:3.12-slim` pinned by its installed digest;
- transport: one fresh user-defined Docker bridge per cell; broker/effect host
  ports publish only on `127.0.0.1`;
- storage and keying: fresh temporary broker/effect SQLite files, consumer
  state, and one-time HMAC material per formal invocation.

The 150 scenarios in a cell share one deliberately injected fault epoch and are
not independent partition/crash events. Profiles reuse scenario IDs and are not
pooled.

## Protocol schedule

For every row, the producer registers state, verifies the check-time receipt,
enqueues the original effect, and applies any frozen invalidation before
consumer A claims the message. Effect substitution replaces only the unclaimed
queued payload and leaves the receipt unchanged.

`partition-before-commit`:

1. consumer A claims all 150 messages without acknowledging them;
2. Docker disconnects A from the experiment bridge;
3. an in-container commit attempt must fail while disconnected;
4. Docker kills A, and the broker recovers exactly its 150 inflight messages;
5. consumer B commits and acknowledges all recovered messages.

`crash-after-commit`:

1. consumer A claims and sends all 150 messages to the effect service without
   acknowledging the broker;
2. Docker kills A;
3. the broker recovers exactly 150 inflight messages;
4. consumer B redelivers, commits, and acknowledges every message.

## Frozen gates

- 600 rows and 600 unique keys; 400 attacks and 200 controls;
- per profile, check-once/receipt-bound stale commits are 100/100 and 0/100;
- every policy/profile preserves 50/50 controls;
- 600/600 messages are claimed by A, recovered only after A is killed, then
  claimed and acknowledged by B;
- partition cells share a verified Docker disconnect and failed in-container
  effect call; crash cells contain 300 successful A-side effect attempts;
- 1,200 broker deliveries, 600 recoveries, and 600 acknowledgements;
- 900 effect attempts: one per partition row and two per crash row;
- allowed rows have exactly one effect; blocked rows have zero;
- crash-profile second attempts are idempotent for all 200 allowed rows;
- all role, loopback-publish, bridge, cleanup, and output-collision gates pass;
- independent daemon-free audit byte-reproduces summary and integrity CSVs.

Any incomplete cell, unexpected partition success, consumer identity failure,
wrong recovery count, output collision, or cleanup failure invalidates the full
attempt. Formal CSVs are written only after all gates pass.

## Exclusions

The result will not establish production broker compatibility, fault
prevalence, broker replication, partition tolerance of broker storage,
cross-database atomicity, WAN behavior, multi-tenant isolation, or independent
administration.
