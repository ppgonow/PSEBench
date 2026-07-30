# INFOCOM Docker queue failover amendment (2026-07-20)

## Trigger

The first pilot failed before any scenario because the pinned offline Python
image lacks PyYAML and a reused HTTP helper introduced an unnecessary transitive
import of the scenario loader.

## Frozen correction before retry

- replace the container service's imported HTTP server with a local
  standard-library JSON request handler;
- replace the container worker's imported HTTP client with a local
  standard-library `urllib` helper;
- do not install packages, pull images, change the pinned image, or change any
  scenario, policy, fault schedule, output field, or acceptance gate;
- rerun syntax, unit, broker-container, effect-container, and worker-connectivity
  preflights before restarting the 40-row pilot from its first cell.

The failed pilot remains excluded in full. A fresh formal invocation is allowed
only after the amended pilot and a new implementation freeze pass.
