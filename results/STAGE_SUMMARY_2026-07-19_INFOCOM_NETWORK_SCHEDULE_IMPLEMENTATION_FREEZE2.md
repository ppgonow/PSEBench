# INFOCOM cross-service schedule implementation freeze 2 (2026-07-19)

This freeze follows the causal-gate amendment. The runner now uses per-attempt
logical mutation-status observations and does not compare timestamps across
service roles.

| File | SHA-256 |
| --- | --- |
| `runner/run_network_schedule_matrix.py` | `23846d603e386738e65cc493099ee624c7ae60c8c4c65b3845466ae32f7a315a` |
| `analysis/audit_network_schedule.py` | `98436a641f5341f83b625939983adad5bb8f9b21fb78828092f41c93b8458502` |
| `tests/test_network_schedule.py` | `0cfcecf75e2c1e1ef5961483e418da8fadde4f0a4ff75bb94800e7716a264bc5` |
| `runner/run_multiprocess_commit_race.py` | `d7101775b113099c30a5664bff9973e340c31da3a1346258d0ffc48d7a62668f` |
| `scenarios/commit-race-heldout/MANIFEST.csv` | `2fcdadacae83242b61754567ba00c61c79a5e4738c676009fac0985f0203b028` |

Python compilation and the four focused schedule/existing-process tests pass.
The pilot must restart with `--overwrite`; no row or timing from the invalid
pilot may be retained.
