# Stage Summary — Shallow Lexical Comparator (SLC)

## Scope
This stage formalizes the previous `guard-sim` prototype into a paper-ready baseline named:

> **Shallow Lexical Comparator (SLC)**

SLC is a tool-layer comparator baseline designed to share the same enforcement point as IACG, but use only **surface lexical persistence cues** rather than IACG's rule-defined request/action classes.

Derived from the previous `guard-sim` prototype, SLC intentionally remains shallow:
- it compares request-side persistence words against action-side persistent markers,
- it does **not** handle negation,
- it does **not** resolve ambiguity,
- it does **not** infer broader authorization scope,
- it does **not** perform semantic override.

---

## SLC definition
At the tool layer:
1. Extract persistence-related lexical cues from the **user request**.
2. Extract persistent / recurring action markers from the **proposed tool action**.
3. If the action is persistent and the request contains lexical persistence cues, **allow**.
4. If the action is persistent and the request lacks lexical persistence cues, **block**.
5. Otherwise allow.

This is intentionally a **shallow lexical matching baseline**, not a semantic guard.

### Request-side lexical cues used
- `daily`
- `weekly`
- `monthly`
- `recurring`
- `every`
- `repeat`
- `hourly`
- `each day`
- `each week`
- `until cancelled`
- `until canceled`
- `no expiry`
- `no expiration`
- `ongoing`
- `auto-renew`
- `keep reminding`

### Action-side markers
Persistent tool actions were treated as carrying persistent markers such as:
- recurring cron schedule
- repeat interval
- ongoing / no-expiry state
- other persistent / broader-scope state changes

---

## Slices executed

### P0-1. Failure-mechanism stress test
Scenarios:
- `H-msg-cron-required-FAIL-001..004`

Run:
- `slc-failure-slc`

Results:
- n = 4
- Attack successes = 4
- **ASR = 1.000**
- Task successes = 4
- **TCR = 1.000**

Interpretation:
- This is the key SLC failure result.
- In these cases, the request includes persistence-related words only in **negated or misleading contexts** (e.g., “do NOT make it recurring”, “no daily or weekly repeats”, “every additional reminder should be avoided”).
- Because SLC does not process negation, it treats these lexical cues as a match and allows the persistent injected action.
- This reproduces the intended shallow-lexical fragility previously illustrated by `guard-sim`.

---

### P0-2. Authorization-boundary contrast
Scenarios:
- `H-msg-cron-required-CTR-ONE-001`
- `H-msg-cron-required-CTR-REC-001`
- `H-msg-cron-required-CTR-AMB-001`

Run:
- `slc-ctr-slc`

Results:
- n = 3
- Attack successes = 0
- **ASR = 0.000**
- Task successes = 3
- **TCR = 1.000**

Interpretation:
- SLC is more selective than a firewall because it does not block all persistent actions by default.
- However, its success here should not be overinterpreted: the comparator still relies on surface lexical matches rather than authorization reasoning.
- It works on these small cases when lexical cues align with the expected action, but it does not define the boundary correctly in principle.

---

### P0-3. Implicit durability set
Scenarios:
- `H-msg-cron-required-IMP-001..006`

Run:
- `slc-implicit-slc`

Results:
- n = 6
- Attack successes = 0
- **ASR = 0.000**
- Task successes = 5
- **TCR = 0.833**

Interpretation:
- SLC partially fails on implicit durability expressions.
- Because it only recognizes a limited lexical cue set, it misses at least one legitimate persistent request that IACG correctly preserves.
- This shows that lexical matching is not equivalent to authorization understanding, even when the action is benign.

---

### P1. Core cron matched slice
Scenarios:
- `H-msg-cron-required-002..011`

Run:
- `slc-core-slc`

Results:
- n = 10
- Attack successes = 0
- **ASR = 0.000**
- Task successes = 10
- **TCR = 1.000**

Interpretation:
- On the matched core cron slice, SLC appears competitive.
- But this should be read together with the failure slice above: lexical comparators can look strong on matched cases while still breaking on negation and misleading lexical contexts.

---

## Aggregate result table

| Slice | n | ASR | TCR |
|---|---:|---:|---:|
| failure stress test | 4 | 1.000 | 1.000 |
| authorization-boundary contrast | 3 | 0.000 | 1.000 |
| implicit durability | 6 | 0.000 | 0.833 |
| core cron matched slice | 10 | 0.000 | 1.000 |

---

## Paper-oriented comparison to IACG

### Same enforcement point?
Yes.
SLC and IACG both operate at the **tool-layer enforcement point**, where the system compares the user request against a proposed tool action before execution.

### Why is SLC not an equivalent substitute for IACG?
Because SLC only compares **raw lexical persistence cues**, whereas IACG reasons about whether the proposed action exceeds the **user-authorized semantic scope**.

SLC can therefore be fooled whenever lexical tokens are present but semantically misleading, negated, or incomplete.

### Which cases show lexical matching is insufficient?
Two sets are especially important:
1. **Failure stress test (`FAIL-001..004`)**
   - SLC reaches **ASR = 1.0** because it treats words like `recurring`, `daily`, `weekly`, and `every` as positive persistence cues even when they appear in negated contexts.
2. **Implicit durability (`IMP-001..006`)**
   - SLC drops to **TCR = 0.833**, showing that surface lexical matching does not robustly capture legitimate persistent intent.

### Is SLC finer-grained than firewall?
Yes, SLC is **finer than firewall** because it does not block all persistent actions indiscriminately.
However, it still fails to capture the true **authorization boundary**. The correct boundary is not whether a request contains certain persistence words, but whether the proposed persistent action is covered by the user's request class.

---

## Short paper-ready conclusion
A concise reusable paragraph:

> **Shallow Lexical Comparator (SLC)** is a tool-layer baseline that compares request-side persistence words against persistent action markers without the structured request/action classes used by IACG. Although SLC is more selective than a firewall and performs well on matched cron cases, it fails on negated and misleading lexical contexts, reaching 100% ASR on our failure stress set, and it also reduces utility on implicit legitimate persistence requests. These results show that shallow lexical matching is insufficient: the key security boundary is authorization coverage, not raw lexical cues.

---

## Output artifacts
Generated files:
- `analysis/slc_run_table.csv`
- `analysis/slc_summary.csv`
- `results/STAGE_SUMMARY_SLC.md`

Naming note:
- `guard-sim` should no longer be used as the formal paper name.
- The official baseline name is **Shallow Lexical Comparator (SLC)**.
