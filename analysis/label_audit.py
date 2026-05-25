#!/usr/bin/env python3
"""Prepare and score a blinded label-audit packet.

The prepare mode creates two CSVs:
- analysis/label_audit_blind_sample.csv: evidence for a second annotator, with
  empty label columns and without run IDs, guard decisions, or stored labels.
- analysis/label_audit_reference.csv: the current stored labels for scoring.

The score mode compares a completed annotator CSV against the reference and
reports observed agreement plus Cohen's kappa for task, attack, and risk labels.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised only in missing deps
    raise SystemExit("PyYAML is required; install with `pip install pyyaml`.") from exc


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
RUNS = ROOT / "results" / "runs"

DEFAULT_QUOTAS = {
    "tool_induction": 12,
    "cron_required": 20,
    "h_web_negative": 6,
    "file_persistence": 10,
    "calendar_recurrence": 10,
    "recipient_hijack": 8,
    "legitimate_persistence_utility": 6,
}

BLIND_FIELDS = [
    "audit_id",
    "slice",
    "scenario_id",
    "family",
    "scenario_type",
    "injection_source",
    "injection_style",
    "target_chain",
    "target_risk",
    "user_intent",
    "required_action",
    "prompt",
    "untrusted_artifacts",
    "task_success_criteria",
    "attack_success_criteria",
    "agent_output",
    "artifact_summary",
    "task_completed",
    "attack_succeeded",
    "risk_level",
    "annotator_notes",
]

REFERENCE_FIELDS = [
    "audit_id",
    "slice",
    "scenario_id",
    "family",
    "run_id",
    "final_json",
    "task_completed_ref",
    "attack_succeeded_ref",
    "risk_level_ref",
    "observed_tools_ref",
    "confirmation_triggered_ref",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def family_id(scenario_id: str) -> str:
    parts = scenario_id.split("-")
    if parts and parts[-1].isdigit():
        return "-".join(parts[:-1])
    return scenario_id


def classify_slice(scenario_id: str, family: str) -> str:
    if scenario_id.startswith("A-"):
        return "tool_induction"
    if family == "H-web-msg-required":
        return "h_web_negative"
    if family in {"H-file-persist-legit", "H-calendar-recurring-legit"}:
        return "legitimate_persistence_utility"
    if family == "H-file-persist-required":
        return "file_persistence"
    if family == "H-calendar-recurring-required":
        return "calendar_recurrence"
    if family == "H-msg-msg-required":
        return "recipient_hijack"
    if family.startswith("H-msg-cron-required"):
        return "cron_required"
    return "supporting_other"


def compact(value: object, limit: int = 900) -> str:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = sanitize_text(re.sub(r"\s+", " ", text).strip())
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def sanitize_text(text: str) -> str:
    text = re.sub(r"/Users/[^,\s\"']+", "<LOCAL_PATH>", text)
    text = re.sub(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        "<UUID>",
        text,
    )
    text = re.sub(r"\b\d{6,}\b", "<NUMERIC_ID>", text)
    text = re.sub(r"\b(Permissive|Strict|Guarded|IACG|Firewall)-mode execution for measurement:\s*", "Execution summary: ", text)
    text = re.sub(r"\b(Permissive|Strict|Guarded|IACG|Firewall)-mode note:\s*", "Execution note: ", text)
    return text


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_or_text(path: Path) -> object:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def load_scenario(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def artifact_summary(run_dir: Path) -> tuple[str, str]:
    agent_output_path = run_dir / "agent_output.txt"
    agent_output = compact(agent_output_path.read_text(encoding="utf-8"), 700) if agent_output_path.exists() else ""

    parts: list[str] = []
    for path in sorted(run_dir.iterdir()):
        if path.name in {"final.json", "scenario.yaml", "decision.json", "agent_raw.json", "meta.json", "run_packet.txt"}:
            continue
        if path.name == "agent_output.txt":
            continue
        if path.name == "cli_events.jsonl":
            events = []
            for line in path.read_text(encoding="utf-8").splitlines()[:8]:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    events.append({"raw": sanitize_text(line)})
                    continue
                safe_event = {
                    "tool": event.get("tool", ""),
                    "ok": event.get("ok", ""),
                }
                if event.get("reason"):
                    safe_event["reason"] = event.get("reason")
                if event.get("target"):
                    safe_event["target"] = sanitize_text(str(event.get("target")))
                if event.get("error"):
                    safe_event["error"] = sanitize_text(str(event.get("error")))
                events.append(safe_event)
            parts.append(f"cli_events={compact(events, 700)}")
            continue
        if path.suffix == ".json":
            parts.append(f"{path.name}={compact(load_json_or_text(path), 500)}")
    return agent_output, " | ".join(parts)


def gather_candidates() -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for final_path in sorted(RUNS.glob("*/*/final.json")):
        final = load_json(final_path)
        labels = final.get("manual_labels") or {}
        if not labels:
            continue

        run_dir = final_path.parent
        run_id = run_dir.parent.name
        scenario_id = run_dir.name
        scenario_path = run_dir / "scenario.yaml"
        if not scenario_path.exists():
            continue
        scenario = load_scenario(scenario_path)
        family = family_id(scenario_id)
        slice_name = classify_slice(scenario_id, family)
        agent_output, artifacts = artifact_summary(run_dir)
        oracle = scenario.get("oracle_expectations") or {}
        intent = scenario.get("intent") or {}

        candidates.append(
            {
                "slice": slice_name,
                "scenario_id": scenario_id,
                "family": family,
                "run_id": run_id,
                "final_json": str(final_path.relative_to(ROOT)),
                "scenario_type": scenario.get("type", ""),
                "injection_source": scenario.get("injection_source", ""),
                "injection_style": scenario.get("injection_style", ""),
                "target_chain": compact(scenario.get("target_chain", "")),
                "target_risk": scenario.get("target_risk", ""),
                "user_intent": intent.get("user_intent", ""),
                "required_action": intent.get("required_action", ""),
                "prompt": compact(scenario.get("prompt", ""), 1400),
                "untrusted_artifacts": compact(scenario.get("artifacts", ""), 1000),
                "task_success_criteria": compact(oracle.get("task_success_if", ""), 700),
                "attack_success_criteria": compact(oracle.get("success_if", ""), 700),
                "agent_output": agent_output,
                "artifact_summary": artifacts,
                "task_completed_ref": str(labels.get("task_completed", "")),
                "attack_succeeded_ref": str(labels.get("attack_succeeded", "")),
                "risk_level_ref": str(labels.get("risk_level", "")),
                "observed_tools_ref": compact(labels.get("observed_tools", "")),
                "confirmation_triggered_ref": str(labels.get("confirmation_triggered", "")),
            }
        )
    return candidates


def balanced_sample(candidates: list[dict[str, object]], quota: int, rng: random.Random) -> list[dict[str, object]]:
    if len(candidates) <= quota:
        return candidates[:]

    buckets: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in candidates:
        buckets[str(row["attack_succeeded_ref"] or "missing")].append(row)
    for rows in buckets.values():
        rng.shuffle(rows)

    labels = sorted(buckets)
    selected: list[dict[str, object]] = []
    if len(labels) > 1:
        per_label = max(1, quota // len(labels))
        for label in labels:
            take = min(per_label, len(buckets[label]), quota - len(selected))
            selected.extend(buckets[label][:take])

    remaining = [row for rows in buckets.values() for row in rows if row not in selected]
    rng.shuffle(remaining)
    selected.extend(remaining[: quota - len(selected)])
    return selected[:quota]


def select_sample(candidates: list[dict[str, object]], seed: int, quotas: dict[str, int]) -> list[dict[str, object]]:
    rng = random.Random(seed)
    by_slice: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in sorted(candidates, key=lambda r: (str(r["slice"]), str(r["scenario_id"]), str(r["run_id"]))):
        by_slice[str(row["slice"])].append(row)

    selected: list[dict[str, object]] = []
    selected_keys: set[tuple[str, str]] = set()
    for slice_name, quota in quotas.items():
        rows = by_slice.get(slice_name, [])
        sample = balanced_sample(rows, quota, rng)
        for row in sample:
            key = (str(row["run_id"]), str(row["scenario_id"]))
            if key not in selected_keys:
                selected.append(row)
                selected_keys.add(key)

    target = sum(quotas.values())
    if len(selected) < target:
        remaining = [
            row
            for row in candidates
            if (str(row["run_id"]), str(row["scenario_id"])) not in selected_keys
        ]
        rng.shuffle(remaining)
        selected.extend(remaining[: target - len(selected)])

    rng.shuffle(selected)
    for idx, row in enumerate(selected, start=1):
        row["audit_id"] = f"LA-{idx:04d}"
    return selected


def summarize_sample(sample: list[dict[str, object]]) -> list[dict[str, object]]:
    stats: dict[str, Counter] = defaultdict(Counter)
    for row in sample:
        sl = str(row["slice"])
        stats[sl]["n"] += 1
        stats[sl][f"attack_{row['attack_succeeded_ref']}"] += 1
        stats[sl][f"task_{row['task_completed_ref']}"] += 1
    rows = []
    for slice_name in sorted(stats):
        counter = stats[slice_name]
        rows.append(
            {
                "slice": slice_name,
                "n": counter["n"],
                "attack_yes": counter["attack_yes"],
                "attack_no": counter["attack_no"],
                "task_yes": counter["task_yes"],
                "task_no": counter["task_no"],
                "task_partial": counter["task_partial"],
            }
        )
    return rows


def prepare(seed: int, output_prefix: Path) -> None:
    candidates = gather_candidates()
    sample = select_sample(candidates, seed, DEFAULT_QUOTAS)

    blind_rows = []
    reference_rows = []
    for row in sample:
        blind_rows.append({field: row.get(field, "") for field in BLIND_FIELDS})
        reference_rows.append({field: row.get(field, "") for field in REFERENCE_FIELDS})

    write_csv(output_prefix.with_name(output_prefix.name + "_blind_sample.csv"), blind_rows, BLIND_FIELDS)
    write_csv(output_prefix.with_name(output_prefix.name + "_reference.csv"), reference_rows, REFERENCE_FIELDS)
    write_csv(output_prefix.with_name(output_prefix.name + "_sample_summary.csv"), summarize_sample(sample))
    print(f"prepared {len(sample)} audit cases from {len(candidates)} labeled finals")
    print(output_prefix.with_name(output_prefix.name + "_blind_sample.csv"))
    print(output_prefix.with_name(output_prefix.name + "_reference.csv"))
    print(output_prefix.with_name(output_prefix.name + "_sample_summary.csv"))


def cohen_kappa(pairs: Iterable[tuple[str, str]]) -> tuple[int, float, float]:
    data = [(a, b) for a, b in pairs if a and b]
    n = len(data)
    if n == 0:
        return 0, 0.0, 0.0
    agree = sum(1 for a, b in data if a == b)
    observed = agree / n
    left = Counter(a for a, _ in data)
    right = Counter(b for _, b in data)
    labels = set(left) | set(right)
    expected = sum((left[label] / n) * (right[label] / n) for label in labels)
    if expected == 1.0:
        kappa = 1.0 if observed == 1.0 else 0.0
    else:
        kappa = (observed - expected) / (1 - expected)
    return n, observed, kappa


def annotator_value(row: dict[str, str], field: str) -> str:
    aliases = {
        "task_completed": ["task_completed", "task_completed_label", "task_completed_b"],
        "attack_succeeded": ["attack_succeeded", "attack_succeeded_label", "attack_succeeded_b"],
        "risk_level": ["risk_level", "risk_level_label", "risk_level_b"],
    }
    for key in aliases[field]:
        value = row.get(key, "").strip()
        if value:
            return value
    return ""


def is_match_value(value: object) -> bool:
    return value is True or str(value) == "True"


def score(annotator_csv: Path, reference_csv: Path, output_prefix: Path) -> None:
    annotator = {row["audit_id"]: row for row in read_csv(annotator_csv)}
    reference = {row["audit_id"]: row for row in read_csv(reference_csv)}
    detail_rows = []
    for audit_id in sorted(reference):
        ref = reference[audit_id]
        ann = annotator.get(audit_id, {})
        detail_rows.append(
            {
                "audit_id": audit_id,
                "slice": ref["slice"],
                "scenario_id": ref["scenario_id"],
                "task_completed_annotator": annotator_value(ann, "task_completed"),
                "task_completed_ref": ref["task_completed_ref"],
                "task_match": annotator_value(ann, "task_completed") == ref["task_completed_ref"],
                "attack_succeeded_annotator": annotator_value(ann, "attack_succeeded"),
                "attack_succeeded_ref": ref["attack_succeeded_ref"],
                "attack_match": annotator_value(ann, "attack_succeeded") == ref["attack_succeeded_ref"],
                "risk_level_annotator": annotator_value(ann, "risk_level"),
                "risk_level_ref": ref["risk_level_ref"],
                "risk_match": annotator_value(ann, "risk_level") == ref["risk_level_ref"],
            }
        )

    summary_rows = []
    for field, ref_field in [
        ("task_completed", "task_completed_ref"),
        ("attack_succeeded", "attack_succeeded_ref"),
        ("risk_level", "risk_level_ref"),
    ]:
        pairs = [(row[f"{field}_annotator"], row[ref_field]) for row in detail_rows]
        n, observed, kappa = cohen_kappa(pairs)
        summary_rows.append(
            {
                "label": field,
                "n_scored": n,
                "observed_agreement": round(observed, 3),
                "cohen_kappa": round(kappa, 3),
            }
        )

    disagreement_rows = []
    for field in ["task_completed", "attack_succeeded", "risk_level"]:
        if field == "task_completed":
            ann_key = "task_completed_annotator"
            ref_key = "task_completed_ref"
            match_key = "task_match"
        elif field == "attack_succeeded":
            ann_key = "attack_succeeded_annotator"
            ref_key = "attack_succeeded_ref"
            match_key = "attack_match"
        else:
            ann_key = "risk_level_annotator"
            ref_key = "risk_level_ref"
            match_key = "risk_match"
        mismatch_rows = [row for row in detail_rows if not is_match_value(row[match_key])]
        confusion = Counter(f"{row[ref_key]}->{row[ann_key]}" for row in mismatch_rows)
        slices = Counter(row["slice"] for row in mismatch_rows)
        disagreement_rows.append(
            {
                "label": field,
                "n_mismatch": len(mismatch_rows),
                "confusion": "; ".join(f"{key}:{value}" for key, value in sorted(confusion.items())),
                "slices": "; ".join(f"{key}:{value}" for key, value in sorted(slices.items())),
            }
        )

    write_csv(output_prefix.with_name(output_prefix.name + "_agreement_detail.csv"), detail_rows)
    write_csv(output_prefix.with_name(output_prefix.name + "_agreement_summary.csv"), summary_rows)
    write_csv(output_prefix.with_name(output_prefix.name + "_disagreement_summary.csv"), disagreement_rows)
    print(output_prefix.with_name(output_prefix.name + "_agreement_summary.csv"))
    print(output_prefix.with_name(output_prefix.name + "_agreement_detail.csv"))
    print(output_prefix.with_name(output_prefix.name + "_disagreement_summary.csv"))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_prepare = sub.add_parser("prepare", help="create blinded audit packet")
    p_prepare.add_argument("--seed", type=int, default=20260523)
    p_prepare.add_argument("--output-prefix", type=Path, default=ANALYSIS / "label_audit")

    p_score = sub.add_parser("score", help="score completed annotator labels")
    p_score.add_argument("annotator_csv", type=Path)
    p_score.add_argument("--reference", type=Path, default=ANALYSIS / "label_audit_reference.csv")
    p_score.add_argument("--output-prefix", type=Path, default=ANALYSIS / "label_audit")
    args = parser.parse_args()

    if args.cmd == "prepare":
        prepare(args.seed, args.output_prefix)
    else:
        score(args.annotator_csv, args.reference, args.output_prefix)


if __name__ == "__main__":
    main()
