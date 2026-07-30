# Container script compatibility amendment (2026-07-18)

The first formal script invocation started the preflight containers but failed
before the matrix because macOS `/bin/bash` 3.2 does not implement the Bash 4
associative-array syntax used by the host wrapper. The Compose trap removed the
containers and network, and no scenario request or result row was produced.

The host wrapper is amended to use ordinary variables and `case` dispatch, so
it remains compatible with the repository's documented macOS shell. This
amendment is recorded before the fresh complete matrix retry; no failed row is
retained, replaced, or counted.
