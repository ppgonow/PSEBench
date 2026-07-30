# INFOCOM Commit-Binding State-Machine Replay (2026-07-15)

## Question and Boundary

Does an action-boundary decision remain valid when security-relevant state
changes between authorization check and external commit? This experiment is a
deterministic local state-machine replay. It does not call a model or service,
create real concurrency, or claim transactional guarantees for downstream
systems.

## Frozen Design

The generator creates 150 scenarios across cron, file, calendar, and message
effects. Each of five families contains 20 attack transitions and 10 matched
stable controls:

| family | pre-registered invalidation |
|---|---|
| effect substitution | normalized commit effect differs from checked effect |
| authorization revocation | authorization version changes before commit |
| principal switch | committing principal differs from authorized principal |
| confirmation replay | one-use confirmation nonce is already consumed |
| lease expiry | commit occurs after receipt expiry |

Every check-time effect is inside its typed authorization envelope. The
generator independently verifies that each attack changes exactly its declared
state condition and that controls preserve all checked fields. The corpus stores
a SHA-256 snapshot of `runner/commit_binding.py` before replay.

`check-once` reuses the successful check result without commit-time validation.
`commit-bound` authenticates a receipt over principal, authorization version,
normalized effect, check/expiry time, and optional confirmation nonce, then
revalidates current commit state. The replay assumes the authentication key and
version/nonce state are monitor-controlled; key compromise and non-atomic nonce
storage are outside this experiment.

## Results

| scope | policy | attack ASR | benign-control TCR |
|---|---:|---:|---:|
| all 5 transitions | check-once | 100/100 | 50/50 |
| all 5 transitions | commit-bound | 0/100 | 50/50 |
| each transition family | check-once | 20/20 | 10/10 |
| each transition family | commit-bound | 0/20 | 10/10 |

The overall Wilson 95% intervals are `[0.963,1.000]` for check-once ASR,
`[0,0.037]` for commit-bound ASR, and `[0.929,1.000]` for both benign-control
TCRs. All 100 attack pairs are discordant in the expected direction; the
two-sided exact McNemar result is `p=1.58e-30`. Each 20-pair family has
`p=1.91e-6`.

## Local Lifecycle Cost

The timing run uses all 150 scenarios, 200 iterations per scenario, and seven
repeats, giving 30,000 samples per operation per repeat.

| operation | median (us) | p95 (us) |
|---|---:|---:|
| check once | 1.125 | 1.250 |
| receipt issue | 9.583 | 10.458 |
| commit verify | 8.541 | 9.333 |
| full bound lifecycle | 17.917 | 19.542 |

These measurements isolate local Python decision logic and exclude model,
network, storage, and external tool latency.

## Interpretation

The result demonstrates a reference-monitor implementation property: a check
must be bound to the principal, authorization state, exact effect, validity
window, and confirmation use observed at commit. It does not estimate how often
these races occur in deployed agents. Real deployments still need atomic nonce
consumption, durable authorization versioning, authenticated principals,
idempotency, retry semantics, and service-specific transaction handling.

## Reproduction

```bash
python3 runner/generate_commit_race_holdout.py \
  --attack-per-family 20 --benign-per-family 10
python3 runner/replay_commit_race.py --policies check-once commit-bound
python3 analysis/summarize_commit_race.py
python3 analysis/benchmark_commit_binding.py --repeats 7 --iterations 200
```
