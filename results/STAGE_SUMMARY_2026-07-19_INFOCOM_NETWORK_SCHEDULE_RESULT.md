# INFOCOM cross-service schedule result (2026-07-19)

## Status

The Freeze 5 formal invocation completed all five profiles and published the
complete 1,500-row matrix only after validation. An independent daemon-free
audit reconstructed the frozen totals and produced a byte-identical summary.
No row from any earlier pilot or failed formal invocation is reused.

The retained amendments document the full execution history: the first pilot
used an invalid cross-process clock comparison; the first formal run exposed
HTTP connection churn; the second exposed accumulated service-lifetime
failure; and the third exposed concurrent SQLite reads on one connection. Each
affected invocation was discarded in full before its dated correction and new
freeze. Freeze 5 serializes all SQLite access and is the sole reported run.

## Frozen outcomes

- rows and unique policy/profile/scenario keys: 1,500 / 1,500;
- profiles: single, delayed 40 ms, duplicate downstream, concurrent retry, and
  forced reordered retry;
- check-once ASR: 100/100 in every fixed profile;
- receipt-bound ASR: 0/100 in every fixed profile;
- TCR: 50/50 for both policies in every fixed profile;
- per-profile same-ID exact McNemar: 100 check-once-only attacks, zero
  receipt-bound-only attacks, `p=1.5777218104420236e-30`;
- per-profile Wilson intervals: `[0.963005,1]` and `[0,0.036995]`;
- every one of 50 profile/policy/family cells contains 20 attacks and 10
  controls with the expected outcome;
- active-mutation gates: 1,000/1,000 attack rows;
- reordered-arrival gates: 300/300 rows, all observing attempt 2 before 1;
- gateway attempts: 2,100;
- effect delivery attempts: 1,600;
- idempotent ledger rows: 1,000.

Benign client median latency for check-once/receipt-bound is 6.535/8.379 ms
(single), 52.081/55.688 ms (delayed), 9.042/10.721 ms (duplicate),
8.878/10.096 ms (concurrent), and 31.838/35.883 ms (reordered). These values
describe the controlled profiles; they are not WAN prevalence or capacity
estimates.

## Public files

| File | SHA-256 |
| --- | --- |
| `analysis/network_schedule_detail.csv` | `59b2880753e159fc4e16b64458124334d094cde861f0f0b29ee1bc07d216f9ec` |
| `analysis/network_schedule_summary.csv` | `f8cfa5999bc085d3eb9c4d52810f0137036d448ef2b3e66dba5b39494da34e67` |
| `analysis/network_schedule_inference.csv` | `2b35b0732a4ef1f694fd6ae976bf79d45d43d41fb61375224eb9c672f0bdcb8d` |
| `analysis/network_schedule_by_family.csv` | `3daeb3b42ed241fffc0f9085a15fe0867d69d9a0599f751a07245d57002fff71` |
| `analysis/network_schedule_paired.csv` | `935bc4430a8593282d0b4ac394acd6f593981ccd9b71712d7de30f550d9f9c4f` |
| `runner/run_network_schedule_matrix.py` | `978b9c72e2b75d4397a0a1286be57a92d9e701734fbc4dc3a65c320375d16581` |
| `analysis/audit_network_schedule.py` | `98436a641f5341f83b625939983adad5bb8f9b21fb78828092f41c93b8458502` |
| `analysis/analyze_network_schedule_results.py` | `c1069084d5912d417719a9474d84eb536fb7ef3b5ec11c6c92fe15c7c140296d` |

Five temporary SQLite files were counted before cleanup and then deleted. All
service processes and client pools terminated. The public artifact contains no
HMAC key, process ID, host identifier, raw crash report, log, or database.
