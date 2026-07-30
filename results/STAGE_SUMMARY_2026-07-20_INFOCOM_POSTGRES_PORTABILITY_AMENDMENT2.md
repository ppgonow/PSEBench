# INFOCOM PostgreSQL portability host-readiness amendment (2026-07-20)

## Reason

Container-local readiness did not guarantee that Docker's loopback port mapping
would accept a host-side Psycopg connection. The first retry failed before any
scenario and wrote no output.

## Single permitted change

After resolving the random loopback port and constructing the in-memory DSN,
the launch script must require one successful host-side Psycopg connection
through that exact DSN before invoking the frozen runner. It retries this
read-only connection gate for at most 15 seconds.

The DSN remains only in an environment variable and is never printed or written.
The image, PostgreSQL version, transaction isolation, scenarios, 30 ms hold,
policies, validation gates, output schema, and cleanup behavior are unchanged.

After shell/static verification and a new script hash record, the next attempt
must start a new disposable container and execute all 540 rows without resume or
overwrite.
