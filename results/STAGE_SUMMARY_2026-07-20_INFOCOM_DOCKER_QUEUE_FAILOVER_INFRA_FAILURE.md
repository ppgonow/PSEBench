# INFOCOM Docker queue failover infrastructure failure (2026-07-20)

## Status

The first 40-row pilot invocation failed before any scenario was registered,
enqueued, claimed, mutated, or committed. No pilot or formal CSV was written.

The broker container exited before its loopback publication could be resolved.
A separate non-reportable container preflight exposed the cause: the slim image
does not include PyYAML, while the container entry point imported the existing
HTTP helper through `run_multiprocess_commit_race.py`, which transitively imports
the YAML scenario loader. The broker and worker logic themselves do not require
YAML.

All failed-pilot and preflight containers and networks were removed. This is an
infrastructure/package-boundary failure, not an experimental outcome.

