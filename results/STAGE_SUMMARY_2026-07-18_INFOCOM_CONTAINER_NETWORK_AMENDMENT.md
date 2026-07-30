# Container-isolated commit-bound replication network amendment (2026-07-18)

## Reason for amendment

The frozen container plan requires host access only through loopback-published
test ports. On Docker Desktop 27.3.1, a user-defined bridge marked
`internal: true` leaves the service's `NetworkSettings.Ports` empty even when a
loopback binding is declared; the host cannot reach the health endpoint. This
was observed during a preflight before any matrix row was executed. Reusing an
existing SQLite file also caused the expected fresh-ledger startup failure;
the runner now allocates a fresh per-run directory.

## Amended topology boundary

The experiment keeps one non-host user-defined Docker `bridge` network, three
distinct service containers and network namespaces, loopback-only published
ports, read-only roots, dropped capabilities, and no-new-privileges. The
containers make no outbound requests and contact no production, third-party,
or user service. The network is not marked Docker `internal` because that
flag prevents the required loopback test ports on this runtime. The experiment
therefore provides same-host namespace and bridge isolation, not an internal
network or a production egress-isolation claim.

The public topology table records `network_internal=0` and the paper must use
the amended wording. This amendment was recorded before the complete 600-row
matrix was run; no failed matrix row is retained or replaced.
