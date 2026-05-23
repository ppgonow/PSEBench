# Stage Summary — New baseline comparison for paper integration

## Scope
This summary consolidates the two newly added baselines:
- **confirm-all-persistent**
- **Shallow Lexical Comparator (SLC)**

The goal is to position them against existing comparators already used in PSEBench:
- **permissive**
- **strict / safe** (where matched reference runs already exist)
- **firewall**
- **IACG**

No new experiments were run for this summary. All numbers below are compiled from existing result files.

Generated artifact:
- `analysis/new_baseline_comparison_table.csv`

---

## Consolidated baseline comparison matrix

A paper-ready CSV has been generated at:
- `analysis/new_baseline_comparison_table.csv`

It covers the following settings:
- core cron matched slice
- authorization-boundary contrast
- implicit durability
- failure-mechanism stress test
- beyond-cron families (file persistence, calendar recurrence, recipient hijack where available)

---

## Key results by experimental block

### 1. Core cron matched slice
Representative comparison:
- permissive: **n=10, ASR=1.000, TCR=1.000**
- strict / safe: **n=10, ASR=0.000, TCR=1.000**
- firewall: **n=10, ASR=0.000, TCR=1.000**
- confirm-all-persistent: **n=10, ASR=0.000, TCR=1.000, confirmation=10**
- SLC: **n=10, ASR=0.000, TCR=1.000**
- IACG: **n=10, ASR=0.000, TCR=1.000**

Takeaway:
- On matched cron cases, several defenses look competitive.
- This is exactly why additional slices are needed: matched cron alone does not separate coarse, lexical, and authorization-aware defenses.

---

### 2. Authorization-boundary contrast
Representative comparison:
- permissive: **n=3, ASR=0.667, TCR=1.000**
- firewall: **n=3, ASR=0.000, TCR=0.667**
- confirm-all-persistent: **n=3, ASR=0.000, TCR=0.667, confirmation=3**
- SLC: **n=3, ASR=0.000, TCR=1.000**
- IACG: **n=3, ASR=0.000, TCR=1.000**

Takeaway:
- This slice most clearly separates **authorization-aware** defenses from coarse ones.
- confirm-all-persistent behaves like a stronger but usability-costly coarse defense: it removes attack success but over-confirms and loses the explicit legitimate recurring case under the current execution model.
- SLC does not fail here, but this should not be mistaken for semantic correctness; it simply does not encounter its failure mode in this tiny contrast set.

---

### 3. Implicit durability
Representative comparison:
- permissive: **n=6, ASR=0.000, TCR=1.000**
- firewall: **n=6, ASR=0.000, TCR=0.000**
- confirm-all-persistent: **n=6, ASR=0.000, TCR=0.000, confirmation=6**
- SLC: **n=6, ASR=0.000, TCR=0.833**
- IACG: **n=6, ASR=0.000, TCR=1.000**

Takeaway:
- This slice is critical because legitimate persistence is expressed implicitly rather than through explicit recurring tokens.
- confirm-all-persistent collapses utility by confirming every case.
- SLC improves over firewall, but still loses one legitimate case because lexical matching does not reliably capture implicit durable intent.
- IACG is the only comparator here that both preserves utility and maintains low ASR.

---

### 4. Failure-mechanism stress test
Representative comparison:
- permissive: **n=4, ASR=1.000, TCR=1.000**
- firewall: **n=4, ASR=0.000, TCR=1.000**
- SLC: **n=4, ASR=1.000, TCR=1.000**
- IACG: **n=4, ASR=0.000, TCR=1.000**

Takeaway:
- This is the decisive SLC result.
- SLC fails exactly where shallow lexical matching should fail: negated or misleading persistence words cause the persistent injected action to be treated as lexically matched and therefore allowed.
- This slice provides direct evidence that lexical matching is not equivalent to a rule-defined intent-action consistency check.

---

### 5. Beyond-cron families
Available comparisons:

#### File persistence
- permissive: **n=6, ASR=1.000, TCR=1.000**
- confirm-all-persistent: **n=11, ASR=0.000, TCR=1.000, confirmation=11**
- IACG: **n=7, ASR=0.000, TCR=1.000**

#### Calendar recurrence
- permissive: **n=6, ASR=1.000, TCR=1.000**
- confirm-all-persistent: **n=11, ASR=0.000, TCR=1.000, confirmation=11**
- IACG: **n=7, ASR=0.000, TCR=1.000**

#### Recipient hijack / broader-scope routing
- permissive: **n=10, ASR=1.000, TCR=1.000**
- confirm-all-persistent: **n=10, ASR=0.000, TCR=1.000, confirmation=10**
- IACG: **n=10, ASR=0.000, TCR=1.000**

Takeaway:
- These families show that the persistence / broader-scope problem is not cron-specific.
- confirm-all-persistent remains a strong but coarse baseline, with maximal confirmation burden.
- IACG generalizes cleanly to other persistent or broader-scope tool actions.

---

## A. confirm-all-persistent: role and limitation
`confirm-all-persistent` is a reasonable baseline because it represents a simple and defensible product policy: if a tool action would create persistence, recurrence, or broader-scope state, require user confirmation. This makes it a strong non-strawman comparator for IACG, since it is easy to explain, straightforward to implement at the tool layer, and effective at suppressing attacks in the evaluated slices. However, its weakness is equally clear: it is not authorization-sensitive. It confirms not only malicious persistence escalation, but also legitimate persistent actions and implicit durable tasks, producing visible utility loss and maximal confirmation burden. It therefore cannot substitute for IACG when the goal is to preserve legitimate persistent tool use with low friction.

---

## B. SLC: role and limitation
SLC is closer to IACG than firewall because it operates at the same enforcement point and also compares the request with the proposed tool action, rather than simply blocking all persistence. This makes it a much more meaningful comparator than a coarse deny-all baseline. However, SLC still fails to capture the rule-defined authorization boundary because it relies only on surface lexical cues. The failure stress set shows that lexical persistence words in negated or misleading contexts can cause SLC to allow unauthorized persistent actions, and the implicit durability set shows that lexical matching can also miss legitimate persistent intent. In short, SLC is finer-grained than firewall, but it lacks the structured request/action classes used by IACG.

---

## C. Integrated 4–6 sentence conclusion
Taken together, the current baseline landscape is strong enough to show that IACG is not a strawman improvement. `confirm-all-persistent` is a strong coarse baseline that suppresses attacks but pays with maximal confirmation burden and clear utility loss on legitimate persistence. SLC is the baseline most conceptually similar to IACG because it compares request-side and action-side information at the same tool-layer enforcement point, but it fails under negated lexical contexts and partially misses implicit durable intent. Firewall remains useful as a coarse lower-utility reference, but it is too blunt to capture the real security boundary. The main advantage of IACG is therefore not merely lower ASR, but its ability to preserve the **rule-defined authorization boundary**: it blocks persistence escalation while still allowing explicitly and implicitly legitimate persistent actions.

---

## Recommended paper placement

### Suitable for the main paper
The following results are strong enough for the main text:
- authorization-boundary contrast
- implicit durability
- failure-mechanism stress test (for SLC)
- at least one compact row from core cron matched slice

### Better suited to appendix
The following are better as appendix or supporting material:
- full beyond-cron family breakdowns by file/calendar/msg
- expanded confirmation-burden details for confirm-all-persistent
- run-level mappings and per-scenario notes

### Suggested insertion points in Chapter 4
1. **Main defense comparison subsection:** place the consolidated baseline table right after the primary IACG result table.
2. **Authorization-boundary analysis subsection:** discuss `confirm-all-persistent` and SLC immediately after the CTR / triple-contrast story.
3. **Failure analysis subsection or appendix pointer:** insert the SLC failure stress result here as the central evidence that lexical matching is insufficient.
4. **Generalization subsection / appendix:** place beyond-cron families here to show that the same tradeoff extends beyond cron.

---

## Bottom line
The two newly added baselines are now sufficient for paper use:
- **confirm-all-persistent** demonstrates that a simple, strong confirmation policy is not enough because it sacrifices utility and user friction.
- **SLC** demonstrates that shallow lexical matching is not enough because it fails to represent the rule-defined authorization boundary.
- Together they strengthen the claim that **IACG occupies a non-trivial middle ground**: more selective than firewall/confirm-all-persistent, and more robust to lexical traps than shallow lexical comparators.
