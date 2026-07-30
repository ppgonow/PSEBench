# INFOCOM Docker queue failover implementation freeze (2026-07-20)

## Status

The amended 40-row pilot passes all protocol and infrastructure gates before
the first formal invocation. The initial pre-scenario packaging failure and its
amendment remain in separate dated reports.

Pilot totals:

- 40 rows and 40 unique keys; 20 attacks and 20 controls;
- check-once/receipt-bound stale commits: 10/0; controls: 20/20;
- partition rows/gates/failed A-side calls: 20/20/20;
- crash rows/successful A-side commit gates: 20/20;
- consumer kill/recovery/B-side gates: 40/40/40;
- broker deliveries/recoveries/acks: 80/40/40;
- effect attempts/effects/nonces: 60/30/2;
- idempotent B-side retries after A committed: 15/15;
- distinct-role, bridge, loopback publication, drain, and cleanup gates: pass.

Pilot CSVs remain under `tmp/` and are not reportable evidence.

## Frozen hashes

| File | SHA-256 |
|---|---|
| `runner/failover_queue.py` | `5f343cefd3c534ecdf2e361c2d985b8736d0d9e37f107cb894c33e76bbfcd8e2` |
| `runner/docker_failover_service.py` | `8be922dc18aec06047f25611ccc605a466c4d8f5a090c54e24c7f57182cbd504` |
| `runner/docker_failover_worker.py` | `f25ea76812877a628cd580c0ef765c9b680d57435c78936b2316e2161b83bbd9` |
| `runner/run_docker_queue_failover.py` | `fd4d64ae80c7fc5ab23e93893292fa8cd9eb9f75a6d9529cc970db4706314f12` |
| `analysis/audit_docker_queue_failover.py` | `0146469a04c20e99c42294ff9225ac0a7068efb996f902adca67a3db34985c85` |
| `tests/test_failover_queue.py` | `85f4b466e29973745ac2582d3562b8b1a66acca60be54297e72af5668597f030` |
| pilot detail | `5c868e996710bfda6318835b4aa0fd905aefec9a82e0e3a524248a7cda7619de` |
| pilot summary | `e1bbd4e73b935d474ebd99f7d74ab0c6c4a9598cb156bc4648464e42abb9027e` |
| pilot integrity | `7644eae0b3419cbb59f6d975851cc8d0b6b7a369e1ccae4f5b4458bb46063b43` |
| pilot metadata | `a12e542fceb4d646def4dbd5fb2a6e9cf4cd9754e6547790d045d952a83ee220` |

The scenario manifest and binding snapshot remain the hashes frozen in the
asynchronous-queue plan. The container image is the locally installed
`python:3.12-slim` image at
`sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de`.

## Formal-run rule

The formal runner must use the complete scenario directory and default
non-overwrite output prefix. Any incomplete fault epoch, unexpected A-side
partition success, wrong recovery count, container/network residue, or matrix
gate failure invalidates the invocation before CSV publication. Any subsequent
code, image, scenario, fault schedule, or policy change requires another dated
amendment and a fresh complete run.
