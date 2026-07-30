# Three-remote-instance commit-bound replication amendment (2026-07-19)

## Reason for amendment

The frozen three-host plan required distinct `/etc/machine-id` values, distinct
endpoint hosts, and direct private TCP reachability. Read-only preflight, before
any scenario request or matrix outcome, established that the available
The authorized remote environments are three Docker instances cloned from one image:
their machine IDs are equal, their SSH connections use one proxy hostname with
different ports, and their overlapping `172.17.0.0/16` container networks are
not mutually routable. The original readiness gate therefore cannot be met and
must not be silently relaxed after observing outcomes.

The same preflight also found distinct boot IDs, DMI product UUIDs, container
cgroup identities, hostnames, PID/network/UTS namespace identities, and
`/proc/cpuinfo` hashes. These signals establish three distinct live remote
container instances. They do not establish three physical machines,
independent administration, or independent failure domains.

## Amended identity and transport boundary

- The reportable deployment is **three authorized remote container instances**,
  one each for authorization, gateway, and effect.
- Readiness requires pairwise-distinct hashes for boot ID, DMI product UUID,
  cgroup identity, hostname, PID/network/UTS namespace identity, CPU-info
  content, and the resolved SSH target-plus-port composite.
- The shared machine-ID hash and shared SSH proxy hostname are retained as
  explicit topology facts; machine ID is no longer treated as an independence
  signal.
- Each service binds only to its remote loopback interface. The client reaches
  authorization and gateway through SSH local forwarding. The gateway reaches
  authorization and effect through SSH reverse forwarding relayed by the
  client host.
- The paper and artifact must describe this path as **SSH-tunneled HTTP**. They
  must not call it a direct private network, independently administered hosts,
  three physical machines, a production deployment, or a distributed
  transaction system.
- Raw hostnames, addresses, ports, SSH configuration, IDs, remote paths, keys,
  logs, and databases stay local. Only SHA-256 identity hashes, non-identifying
  capability fields, service-role identities, and aggregate integrity evidence
  may enter the public artifact.

## Unchanged frozen matrix and causal gate

- The existing 150 scenarios, five families, four policies, and 600 unique
  policy/scenario observations remain fixed.
- Mutation hold remains 1,000 ms; the post-observation delay remains 10 ms;
  authorization-state and effect-service delays remain 0.5 ms.
- For every attack row, the client must observe `mutation_applied` and not
  `mutation_completed`, wait the fixed delay, observe the same active state
  again, and only then send the gateway commit request. No clocks from different
  instances are compared.
- Duplicate-delivery, SQLite idempotence, complete-matrix, paired-test, and
  no-row-replacement requirements are unchanged.
- Results remain a separate remote-instance replication and are never pooled
  with the process or same-host Docker matrices as independent scenarios.

## Fresh readiness and reportability gates

- Key-only `BatchMode=yes` SSH succeeds for all three aliases.
- Python 3.10 or newer and the frozen service dependencies are available.
- All amended identity fields satisfy the distinct/shared expectations above.
- Authorization, gateway, and effect health responses match their assigned
  logical instance identities through the actual tunnels.
- Gateway-to-authorization and gateway-to-effect probes pass through the relay
  before a scenario request is sent.
- Remote run directories, authentication-key files, and the effect ledger are
  newly allocated; cleanup removes key material and terminates all services and
  tunnels.
- Exactly 600 rows and 600 unique keys are produced, all 400 attack rows pass
  the logical active-mutation gate, ledger and retry invariants hold, and a
  daemon-free audit reproduces summaries and paired tests from public files.

Any failed readiness gate aborts before the matrix. Any infrastructure failure
during the matrix invalidates the whole attempt; no failed or missing row may be
dropped, replaced, or combined with another attempt. A further protocol change
requires another dated amendment before retry.
