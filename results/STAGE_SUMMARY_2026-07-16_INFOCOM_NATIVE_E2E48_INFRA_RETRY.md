# Native E2E48 Infrastructure Retry Record (2026-07-16)

The first complete v2 pass attempted all 288 fixed keys and consumed 1,008
HTTP attempts. It produced 281 complete rows and seven unresolved
infrastructure rows:

- three proxy disconnects that exhausted the existing two-retry allowance;
- four HTTP 500 responses explicitly labeled `Database error` by the endpoint.

The HTTP 500 database failures had received only one attempt because 500 was
not initially included in the transient-status set. Before resume, status 500
was added to the same fixed maximum of two retries already applied to 429,
502, 503, 504, connection, and timeout failures. This changes no model prompt,
tool, policy, scenario, outcome rule, statistical unit, or request ceiling.

Resume re-executes only unresolved keys, clears any partial SQLite state for
that key first, retains every failed raw row for audit, and continues the
cumulative 1,800-attempt budget. Successful units are not repeated. The latest
valid row for a fixed model/policy/scenario key is the only row eligible for
summary.

