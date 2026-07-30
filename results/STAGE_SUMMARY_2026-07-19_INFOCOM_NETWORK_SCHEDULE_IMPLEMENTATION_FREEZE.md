# INFOCOM cross-service schedule implementation freeze (2026-07-19)

The plan in `STAGE_SUMMARY_2026-07-19_INFOCOM_NETWORK_SCHEDULE_PLAN.md` is
implemented and the focused unit/integration tests pass before any pilot or
formal result is observed.

| File | SHA-256 |
| --- | --- |
| `runner/run_network_schedule_matrix.py` | `fe1d70e61b1e24b43087a056931b2c77a3c6b545d74515907cdceeea13fc6692` |
| `analysis/audit_network_schedule.py` | `98436a641f5341f83b625939983adad5bb8f9b21fb78828092f41c93b8458502` |
| `tests/test_network_schedule.py` | `0cfcecf75e2c1e1ef5961483e418da8fadde4f0a4ff75bb94800e7716a264bc5` |
| `runner/run_multiprocess_commit_race.py` | `d7101775b113099c30a5664bff9973e340c31da3a1346258d0ffc48d7a62668f` |
| `scenarios/commit-race-heldout/MANIFEST.csv` | `2fcdadacae83242b61754567ba00c61c79a5e4738c676009fac0985f0203b028` |

Pre-pilot checks:

- Python compilation passes for the runner, auditor, and tests;
- four focused network-schedule and existing multi-process tests pass;
- the reordered integration test observes logical attempt 2 before attempt 1;
- check-once commits two reordered invalid deliveries into one ledger row;
- receipt-bound blocks both reordered invalid attempts before effect delivery.

The non-reportable pilot command is:

```bash
env LC_ALL=C LANG=C python3 \
  runner/run_network_schedule_matrix.py --pilot --overwrite
```

No public CSV is written by the pilot. Any subsequent code or protocol change
requires a dated amendment before the formal run.
