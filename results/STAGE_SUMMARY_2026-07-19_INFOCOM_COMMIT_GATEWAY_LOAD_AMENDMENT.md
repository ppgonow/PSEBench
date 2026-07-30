# INFOCOM commit-gateway load runtime amendment (2026-07-19)

## Invalid first attempt

The first reportable command resolved `python3` to Apple system Python 3.9.6.
During concurrent loopback connection setup, `urllib` raised
`OSError: [Errno 22] Invalid argument` while setting `TCP_NODELAY`. The runner
terminated before writing either public detail or summary CSV. Its incomplete
temporary SQLite ledger is non-reportable and will be replaced in full; no row,
condition, or timing from this attempt is retained.

## Frozen correction

The rerun changes only the interpreter to the repository virtual environment,
`.venv/bin/python` (Python 3.14.2 with the installed project dependencies). The
runner, service code, auditor, tests, manifest, policies, concurrency levels,
repeats, request counts, warm-up, delays, ordering, metrics, and acceptance
conditions remain byte-for-byte or value-for-value identical to the original
plan. The complete matrix restarts from its first condition with `--overwrite`.

```bash
env LC_ALL=C LANG=C .venv/bin/python \
  runner/benchmark_commit_gateway_load.py --overwrite
```

Only a complete 3,600-request output that passes the independent audit is
reportable.
