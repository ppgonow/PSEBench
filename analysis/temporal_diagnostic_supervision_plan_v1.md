# Supervised temporal authorization diagnostic: proposed next run

Status: design proposal only; no scenarios frozen and no inference scheduled.
The parent agent reviewed a read-only subagent critique of the local v2b
factorial. The subagent inherited the current model; no external endpoint was
used. No lower model price or token saving has been established.

## Decision

Retain the observed v2b results, including all errors. Focus the next
development experiment on concrete temporal scope. Do not claim that
contaminated framing increased ASR or that the previous reject-all result
establishes useful authorization discrimination.

Proposed matrix: 24 base task instances × two proposal types (authorized
dates / an extra unauthorized date) × two authorization expressions
(explicit / paraphrased) × two framings (neutral / contaminated) × two
decision procedures (ordinary / model-extracted date-set comparison) = 384
local calls. These are repeated conditions of 24 base instances, not 384
independent samples. Template dependence must also be disclosed.

Use only concrete effects, fix balanced instructions and structured output,
and have the model extract date sets rather than showing it oracle answers.
Keep hidden canonical grants for offline label validation; check explicitly
authorized proposals and added-date violations before any inference.
Model-derived date comparisons must remain separate from trusted execution
grants. A supervisor model is neither ground truth nor a post-state observer.

## Division of work

- Execution worker: construct the development instances and frozen matrix,
  run local requests only after preflight, preserve every row and error.
- Review worker: inspect labels, hashes, all planned keys, and denominator
  accounting without changing outcomes or discarding failures.
- Parent agent: decide whether a protocol is ready, review contradictory
  outcomes, and determine which conclusions are justified.

Use short summaries with file paths and exact counts. For future delegations,
prefer fresh task context containing only necessary local paths and
constraints. Do not include credentials or entire conversation histories.
Any future external supervisor needs separately verified model availability,
price, non-secret endpoint binding, and environment-only credentials. Its
identity and usage must be logged separately from benchmark models.
