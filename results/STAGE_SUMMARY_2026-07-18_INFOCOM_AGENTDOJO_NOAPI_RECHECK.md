# AgentDojo official no-API recheck (2026-07-18)

## Scope

This stage re-runs the official local test suites independently after the
native GPT-5.4/GPT-5.6 extension. It is an interface and installation health
check only; it sends no model request, uses no credential, and produces no
AgentDojo ASR/TCR performance result.

## Results

- AgentDojo official repository: `32 passed`, one Python 3.14 deprecation
  warning.
- AgentDojo-Core official repository: `21 passed`, one Python 3.14 deprecation
  warning.
- The two suites were collected in separate processes to avoid their shared
  test-module basenames causing pytest import collisions.
- `python -m agentdojo.scripts.benchmark --help` exposes the official
  `OPENAI_COMPATIBLE` model path and the expected workspace/attack/defense
  options.

## Boundary

The previously attempted official live smoke remains blocked at the endpoint
with HTTP 403 and is not a performance row. A new live native smoke or an
independent-provider experiment requires a freshly rotated credential that has
not appeared in chat. The exposed relay key is not reused.
