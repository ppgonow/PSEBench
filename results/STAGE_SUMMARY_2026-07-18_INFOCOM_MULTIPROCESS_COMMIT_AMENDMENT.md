# Multiprocess commit experiment infrastructure amendment (2026-07-18)

## Invalid first attempt

The first complete-matrix command used the runner defaults: a 2 ms delay before
the gateway request and an 8 ms authorization-mutation hold. The integrity gate
stopped the run at validation because the first reported attack row did not
record overlapping request intervals. No JSONL or derived CSV was written, and
the incomplete SQLite database is not a reportable result.

This is an orchestration failure rather than a policy outcome. The process and
HTTP scheduling overhead can exceed the original 8 ms overlap window.

## Frozen retry change

The complete matrix will restart from a fresh database with exactly one
parameter change:

```bash
python3 runner/run_multiprocess_commit_race.py \
  --mutation-hold-ms 30 \
  --overwrite
```

The commit delay remains 2 ms, authorization-state and effect-service delays
remain 0.5 ms, all 150 scenarios and four policies remain unchanged, and all
600 observations must pass the original PID, timing, retry, ledger, and pairing
checks. This amendment is recorded before the retry outcome is observed.
