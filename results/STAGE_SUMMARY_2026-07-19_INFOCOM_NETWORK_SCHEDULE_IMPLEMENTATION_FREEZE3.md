# INFOCOM cross-service schedule implementation freeze 3 (2026-07-19)

This freeze follows transport amendment 2. The schedule protocol is unchanged;
only bounded persistent connection management is enabled for this experiment.

| File | SHA-256 |
| --- | --- |
| `runner/run_network_schedule_matrix.py` | `de20be23772cbadb641938da53c04f1e045428dc6d99d1b89ee3e74a25da0b31` |
| `analysis/audit_network_schedule.py` | `98436a641f5341f83b625939983adad5bb8f9b21fb78828092f41c93b8458502` |
| `tests/test_network_schedule.py` | `86ed34d38bb4697c074b24287803d264dcfabe1224dcc2583c8c5fbe686a7af7` |
| `runner/run_multiprocess_commit_race.py` | `d7101775b113099c30a5664bff9973e340c31da3a1346258d0ffc48d7a62668f` |
| `scenarios/commit-race-heldout/MANIFEST.csv` | `2fcdadacae83242b61754567ba00c61c79a5e4738c676009fac0985f0203b028` |

Python compilation and all four focused schedule/existing-process tests pass.
The pilot and formal commands must both restart with `--overwrite`; the invalid
formal database is diagnostic-only and must not be reused.
