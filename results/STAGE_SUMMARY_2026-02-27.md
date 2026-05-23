# Stage Summary (as of 2026-02-27 23:55 Asia/Shanghai)

## Goal alignment
Target venue: **top-tier CS security conference** (IEEE S&P / USENIX Security / CCS / NDSS).
We focus on a black-box-first benchmark for **tool-chain induced risk** in agent frameworks.

This update emphasizes the *hybrid* suite where benign tasks legitimately require tools,
which is where we can observe meaningful non-zero ASR under permissive policies.

---

## Repository snapshot
- Repo: `PSEBench`
- Runner is still "black-box-first" (does not auto-control OpenClaw), but we have many labeled runs under `results/runs/**/final.json`.
- NOTE: `results/**` is git-ignored by default; keep summaries/aggregates in `analysis/` for cloud sync.

---

## Aggregate results (from existing manual_labels)
We parsed **141** labeled `final.json` files.

### By group
- **A (attack-only web/nodes/msg-cron)**: n=27, **ASR=0.00** (0/27), TCR yes=24, partial=3
- **H (hybrid required)**: n=114, **ASR=0.447** (51/114), TCR yes=114

Interpretation:
- A-suite is mostly *easy to defend* under the current instruction templates (ignore injected instructions).
- H-suite is the main signal: when the agent must use tools (cron/message), permissive policies lead to **persistence-style injection success**.

### Tool & risk profile (H-suite)
- Observed tools in labeled runs: cron (107), message (59), browser (28)
- In **attack_yes** cases: cron (51), message (25)
- All attack_yes labeled risk levels are **R2** (persistence / recipient manipulation class)

---

## Key finding worth writing up
A clear separation emerges:
- **Strict / safe** variants: ASR ~ 0 with TCR preserved.
- **Naive / permissive** variants: ASR becomes high (often ~1.0 on the cron-required slice), primarily via **recurring cron persistence** when injected text suggests "also make it hourly / forever" using:
  - policy-impersonation ("POLICY: ...")
  - system-impersonation ("[SYSTEM] ...")
  - urgency framing
  - code-block cron snippets

This supports a paper story around *tool-gating / confirmation* and *persistence safeguards*.

---

## Engineering progress tonight
- Added script to aggregate manual labels:
  - `analysis/aggregate_manual_labels.py`
  - outputs:
    - `analysis/manual_aggregate_by_group.csv`
    - `analysis/manual_aggregate_by_run.csv`
    - `analysis/manual_aggregate_by_scenario.csv`

---

## Immediate next experiments (safe for OpenClaw + Telegram)
These are designed to **not change** gateway/channel config and avoid Telegram spam.
1) Expand H-msg-cron-required variants focusing on *recipient change* and *schedule escalation* but keep delivery sandboxed.
2) Add a minimal "persistence guard" condition (e.g., require explicit user confirmation for recurring cron) and rerun the same H suite to quantify ASR drop vs TCR.
3) Create a small 2×2 matrix:
   - strict vs permissive
   - with vs without persistence guard

---

## How to reproduce the aggregate
```bash
cd PSEBench
python3 analysis/aggregate_manual_labels.py
```
