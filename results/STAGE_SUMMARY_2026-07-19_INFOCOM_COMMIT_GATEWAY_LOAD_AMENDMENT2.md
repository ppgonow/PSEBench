# INFOCOM commit-gateway load transport amendment 2 (2026-07-19)

## Invalid second attempt

The interpreter-only correction in the first amendment did not resolve the
failure.  The complete rerun under repository Python 3.14.2 again terminated
before writing either public detail or summary CSV.  The failure was the same
macOS loopback `TCP_NODELAY` `EINVAL` raised during concurrent short-lived HTTP
connection creation.  The temporary SQLite ledger is non-reportable and will
be replaced in full.  No request, condition, or timing from either failed
attempt is retained.

## Frozen transport correction

The third attempt changes only HTTP connection management for this load
benchmark:

- the loopback JSON services advertise HTTP/1.1 and explicit content lengths;
- a bounded standard-library connection pool establishes loopback connections
  sequentially before concurrent measurement;
- the gateway uses pooled authorization/effect connections only when
  `ServiceCluster(pooled_http=True)` is requested;
- the original 600-row safety matrix retains its existing non-pooled default;
- the load client uses the same bounded persistent-connection mechanism.

The policies, stable scenario, concurrency levels (1, 8, 32), three repeats,
200 measured requests per condition, 10 warm-up requests, alternating policy
order, 0.5 ms authorization/effect delays, metrics, and acceptance conditions
remain unchanged.  A non-reportable concurrency-32 pilot with 50 measured
requests per policy must pass before the full matrix.  The pilot writes no
public analysis CSV.  The
reportable run then restarts from the first condition with `--overwrite` and
replaces the temporary database.

```bash
env LC_ALL=C LANG=C .venv/bin/python \
  runner/benchmark_commit_gateway_load.py --pilot --overwrite

env LC_ALL=C LANG=C .venv/bin/python \
  runner/benchmark_commit_gateway_load.py --overwrite
```

Only one uninterrupted 3,600-request output that passes the independent audit
is reportable.
