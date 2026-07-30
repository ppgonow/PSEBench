# INFOCOM official-oracle state-hash amendment (2026-07-31)

## Trigger

A clean rerun of the frozen 16-case official AgentDojo oracle audit reproduced
all oracle labels, observed effects, summaries, and integrity totals, but two
calendar rows differed in `post_state_sha256`. Inspection showed that the
official calendar fixture stores event participants through a set-like
container whose list serialization order varies with Python's process hash
seed. The semantic state and both oracle decisions were unchanged.

## Amendment

Before any further released-output regeneration, state hashing will canonicalize
only fields with set semantics (`participants` and `recipients`) by recursively
normalizing their values and sorting the resulting list. Ordered histories and
all other list-valued fields retain their original order. The official task
predicate, grant-relative predicate, frozen manifest, state mutation, observed
effect extraction, and all labels remain unchanged.

## Boundary

This is a deterministic serialization repair, not a new experiment or a result
selection. All 16 rows must be regenerated together from the frozen manifest.
The regenerated detail, summary, and integrity files must then byte-match a
second clean process. Any change to a label, case count, family balance, source
revision, or manifest hash invalidates the repair.
