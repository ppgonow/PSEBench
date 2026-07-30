# INFOCOM Docker queue failover result (2026-07-20)

## Outcome

The first formal invocation after the packaging amendment completed the frozen
600-row matrix. CSVs were written only after every outcome, partition/crash,
consumer ownership, recovery, idempotence, topology, and cleanup gate passed.
The earlier pre-scenario pilot failure remains excluded and documented.

| Fault profile | Policy | Stale commits | Controls complete | Broker deliveries | Effect attempts | Effects |
|---|---|---:|---:|---:|---:|---:|
| crash after commit | check-once | 100/100 | 50/50 | 300 | 300 | 150 |
| crash after commit | receipt-bound | 0/100 | 50/50 | 300 | 300 | 50 |
| partition before commit | check-once | 100/100 | 50/50 | 300 | 150 | 150 |
| partition before commit | receipt-bound | 0/100 | 50/50 | 300 | 150 | 50 |

The matrix contains 600 rows and 600 unique profile/policy/scenario keys, 400
attack rows, and 200 controls. Every row is first claimed by consumer A, then
recovered only after Docker confirms A has been killed, claimed by consumer B,
and acknowledged exactly once. Totals are 1,200 broker deliveries, 600 owner
recoveries, 600 acknowledgements, 900 effect-service attempts, 400 effect rows,
20 nonce consumptions, and zero queued/inflight messages after each cell.

The two partition cells share one Docker network-disconnect epoch each. Their
in-container A-side effect call fails while disconnected, after which B performs
the sole effect attempt. The two crash cells share one kill epoch each after A
has issued all 150 effect attempts but before any broker acknowledgement. B then
redelivers all messages; all 200 allowed crash-profile rows report an idempotent
second attempt and one effect, while receipt-bound attack rows block twice.

## Interpretation

The result strengthens the asynchronous reference by injecting actual Docker
network loss and abrupt consumer termination rather than only logical broker
restart or acknowledgement loss. A cached enqueue-time allow remains stale
after either fault. Receipt-bound verification at the surviving consumer's
effect boundary blocks all invalidated messages and preserves controls.

The 150 rows in each cell share one fault epoch and are not 150 independent
partition/crash events. The broker remains a PSEBench SQLite-backed reference;
the result does not establish production broker compatibility, broker-storage
partition tolerance, replicated consensus, WAN behavior, multi-tenant
isolation, or independent administration.

## Infrastructure and cleanup

Each cell creates four distinct containers on a fresh Docker bridge: broker,
effect, consumer A, and consumer B. Broker/effect publications bind random ports
only on `127.0.0.1`. The installed `python:3.12-slim` image is pinned at
`sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de`.
No image or package was downloaded during execution.

All containers and networks were removed after every cell. Temporary broker,
effect, consumer-state, WAL, HMAC, port, container-identity, and runtime-log
material is absent from public output. The daemon-free auditor reconstructs the
summary and integrity CSVs byte-for-byte from detail and public metadata.

## Public file hashes

| File | SHA-256 |
|---|---|
| `analysis/docker_queue_failover_detail.csv` | `69c3fda6b630fc71efdb674fc76c35a67d2312e5beda5746079b49526c6f0f74` |
| `analysis/docker_queue_failover_summary.csv` | `25efaa6703b98175f9bb46b5cdadfe49d3da5e85284024f703207c3a5e13dfb4` |
| `analysis/docker_queue_failover_integrity.csv` | `b49ed5ccdd4fd813ef703f20ed5a2e1612a0f29f0e0006e9e89d9996db5d9fc7` |
| `analysis/docker_queue_failover_metadata.csv` | `04c0395af7e0185a393b8864fd747be8e1c53af5da6f81663c1e5cd7fd24cfe6` |
| `runner/failover_queue.py` | `5f343cefd3c534ecdf2e361c2d985b8736d0d9e37f107cb894c33e76bbfcd8e2` |
| `runner/docker_failover_service.py` | `8be922dc18aec06047f25611ccc605a466c4d8f5a090c54e24c7f57182cbd504` |
| `runner/docker_failover_worker.py` | `f25ea76812877a628cd580c0ef765c9b680d57435c78936b2316e2161b83bbd9` |
| `runner/run_docker_queue_failover.py` | `fd4d64ae80c7fc5ab23e93893292fa8cd9eb9f75a6d9529cc970db4706314f12` |
| `analysis/audit_docker_queue_failover.py` | `0146469a04c20e99c42294ff9225ac0a7068efb996f902adca67a3db34985c85` |
| `tests/test_failover_queue.py` | `85f4b466e29973745ac2582d3562b8b1a66acca60be54297e72af5668597f030` |
