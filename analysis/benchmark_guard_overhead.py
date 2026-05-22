#!/usr/bin/env python3
from __future__ import annotations

import csv
import statistics as stats
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "scenarios"
OUT_CSV = ROOT / "analysis" / "iacg_overhead_summary.csv"
OUT_TRACE = ROOT / "analysis" / "iacg_overhead_runs.csv"

sys.path.insert(0, str(ROOT / "runner"))
from run_hybrid_cli import extract_slc_request_cues, infer_intent  # noqa: E402


def scenario_files() -> list[Path]:
    files: list[Path] = []
    for path in SCENARIOS.rglob("*.yaml"):
        if "_assets" in path.parts:
            continue
        files.append(path)
    return sorted(files)


def load_corpus() -> list[dict]:
    corpus: list[dict] = []
    for path in scenario_files():
        with path.open("r", encoding="utf-8") as f:
            sc = yaml.safe_load(f)
        if not isinstance(sc, dict):
            continue
        prompt = str(sc.get("prompt", "")).strip()
        intent = sc.get("intent") or {}
        risk = sc.get("risk") or {}
        required_action = str(intent.get("required_action", "")).strip()
        user_intent = str(intent.get("user_intent", "")).strip()
        escalation = str(risk.get("escalation", "")).strip()
        type_ = str(sc.get("type", "")).strip()
        if "persistent" in required_action or "recurring" in required_action or user_intent == "recurring" or escalation == "persistence":
            action_kind = "persistent"
        elif escalation == "recipient_hijack" or "hijack" in required_action:
            action_kind = "broader-scope"
        elif type_ == "attack" and user_intent == "none":
            action_kind = "persistent"
        else:
            action_kind = "one-shot"
        corpus.append(
            {
                "id": sc.get("id", path.stem),
                "path": str(path.relative_to(ROOT)),
                "prompt": prompt,
                "action_kind": action_kind,
                "user_intent": user_intent,
                "required_action": required_action,
                "escalation": escalation,
            }
        )
    return corpus


def bench_policy(name: str, corpus: list[dict], loops: int, repeats: int):
    def no_op(item: dict):
        return "allow"

    def firewall(item: dict):
        return "block" if item["action_kind"] != "one-shot" else "allow"

    def confirm_all_persistent(item: dict):
        return "require_confirmation" if item["action_kind"] != "one-shot" else "allow"

    def iacg(item: dict):
        intent, _ = infer_intent(item["prompt"])
        if intent == "one-shot" and item["action_kind"] != "one-shot":
            return "block"
        return "allow"

    def slc(item: dict):
        cues = extract_slc_request_cues(item["prompt"])
        if item["action_kind"] != "one-shot" and not cues:
            return "block"
        return "allow"

    policies = {
        "allow-only": no_op,
        "firewall": firewall,
        "confirm-all-persistent": confirm_all_persistent,
        "SLC": slc,
        "IACG": iacg,
    }
    fn = policies[name]

    samples = []
    start = time.perf_counter_ns()
    for _ in range(repeats):
        t0 = time.perf_counter_ns()
        sink = 0
        for _ in range(loops):
            for item in corpus:
                out = fn(item)
                sink ^= 1 if out == "allow" else 0
        elapsed = time.perf_counter_ns() - t0
        per_decision_us = elapsed / (loops * len(corpus)) / 1000.0
        samples.append(per_decision_us)
        # keep sink alive so Python cannot optimize away the loop
        if sink == -1:
            print("impossible")
    total_elapsed = time.perf_counter_ns() - start
    return {
        "policy": name,
        "corpus_n": len(corpus),
        "loops": loops,
        "repeats": repeats,
        "median_us": stats.median(samples),
        "mean_us": stats.mean(samples),
        "p95_us": stats.quantiles(samples, n=20)[18] if len(samples) > 1 else samples[0],
        "min_us": min(samples),
        "max_us": max(samples),
        "total_seconds": total_elapsed / 1e9,
    }, samples


def main() -> None:
    corpus = load_corpus()
    if not corpus:
        raise SystemExit("No scenarios loaded for overhead benchmark.")

    loops = 2000
    repeats = 7

    summaries = []
    traces = []
    for policy in ["allow-only", "firewall", "confirm-all-persistent", "SLC", "IACG"]:
        summary, samples = bench_policy(policy, corpus, loops, repeats)
        summaries.append(summary)
        for idx, sample in enumerate(samples, start=1):
            traces.append({"policy": policy, "repeat": idx, "us_per_decision": round(sample, 6)})

    base = next(r for r in summaries if r["policy"] == "allow-only")
    base_median = base["median_us"]
    for row in summaries:
        row["relative_to_allow_only"] = round(row["median_us"] / base_median, 2) if base_median else 0.0

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "policy",
                "corpus_n",
                "loops",
                "repeats",
                "median_us",
                "mean_us",
                "p95_us",
                "min_us",
                "max_us",
                "relative_to_allow_only",
                "total_seconds",
            ],
            lineterminator="\n",
        )
        w.writeheader()
        for row in summaries:
            w.writerow(row)

    with OUT_TRACE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["policy", "repeat", "us_per_decision"], lineterminator="\n")
        w.writeheader()
        for row in traces:
            w.writerow(row)

    print(OUT_CSV)
    print(OUT_TRACE)


if __name__ == "__main__":
    main()
