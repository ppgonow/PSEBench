# Stage Summary (as of 2026-03-06 15:52 Asia/Shanghai)

## Major update
We successfully fixed the local OpenClaw gateway auth mismatch and resumed execution-backed cron experiments. We have now completed a first **2×2-style guard/policy matrix slice** over the `H-msg-cron-required` family.

### Local execution issue that was fixed
A development-environment gateway authentication mismatch was resolved before collecting the CLI-backed cron measurements. No credential values are recorded in this artifact.

---

## Completed experiment groups
All groups below cover the full 10-scenario set:
- `H-msg-cron-required-002` ... `011`

### Group A: `g1fixed-permissive`
- runner/policy: decision-proxy, `naive`
- n = 10
- attack successes = 10
- **ASR = 1.0**
- **TCR = 1.0**

### Group B: `g1fixed-strict-guard`
- runner/policy: decision-proxy, `strict`
- n = 10
- attack successes = 0
- **ASR = 0.0**
- **TCR = 1.0**

### Group C: `g2-permissive-guard`
- runner/policy: CLI safe path (no injected recurring execution)
- n = 10
- attack successes = 0
- **ASR = 0.0**
- **TCR = 1.0**

### Group D: `g2-strict-noguard`
- runner/policy: decision-proxy, `strict`
- n = 10
- attack successes = 0
- **ASR = 0.0**
- **TCR = 1.0**

---

## Statistical snapshot
Wilson 95% confidence intervals:
- 1.0 -> [0.722, 1.000]
- 0.0 -> [0.000, 0.278]
- all TCR values in these groups are 1.0 -> [0.722, 1.000]

Key Fisher exact comparisons:
- `g1fixed-permissive` vs `g2-permissive-guard`: **p = 1.08e-05**
- `g2-strict-noguard` vs `g1fixed-strict-guard`: **p = 1.0**

---

## What the new matrix tells us
### Strong conclusion
A **permissive + guard** condition (`g2-permissive-guard`) reduces ASR from **1.0 to 0.0** relative to the permissive baseline, while preserving TCR at **1.0**.

This is important because it shows the project does **not** need to rely only on a globally strict policy to control the cron persistence failure mode.

### Additional conclusion
`strict-noguard` and `strict-guard` are indistinguishable in this slice (both 0/10 attack success, both 10/10 task success).

Interpretation:
- the strict policy also prevents recurring persistence in this scenario family,
- the guard is therefore most valuable for **permissive/autonomous** settings.

---

## Caveat
The current matrix still mixes two runner styles:
- decision-proxy strict/naive groups,
- CLI safe-path group for permissive+guard.

So the paper should describe this honestly as a controlled black-box evaluation slice, not a single uniform live-agent implementation of all four conditions.

That said, the scientific takeaway is much stronger now:
- the permissive baseline is attack-prone,
- adding a narrow persistent-state restriction removes the observed failures,
- strict policy already behaves safely in this family,
- benign task completion remains intact in all four groups.

---

## Analysis artifacts added
- `analysis/g1_guard_summary.csv`
- `analysis/g2_guard_matrix_summary.csv`

---

## Bottom line
Today materially strengthened the paper:
1. we fixed a real execution blocker,
2. resumed valid cron experiments,
3. completed a usable first matrix showing:
   - permissive: **10/10 attacks**
   - permissive + guard: **0/10 attacks**
   - strict: **0/10 attacks**
   - strict + guard: **0/10 attacks**
4. all four groups preserved benign task completion at **10/10**.

The most important new claim now supported is:
> a **narrow persistence guard** can eliminate the observed cron-persistence failures even in a permissive setting, without reducing TCR in this slice.
