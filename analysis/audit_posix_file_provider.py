#!/usr/bin/env python3
"""Run and audit the frozen sandboxed POSIX provider conformance corpus."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import json
import os
import platform
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from posix_file_service import (  # noqa: E402
    CommitResult,
    PosixFileSandbox,
    PosixPostStateObserver,
)


PROFILES = (
    "clean-create",
    "target-symlink",
    "parent-symlink",
    "target-hardlink",
    "parent-swap",
    "aggregate-budget",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _mutate(sandbox: PosixFileSandbox, case: dict[str, Any]) -> None:
    profile = case["profile"]
    target = sandbox.host_path(case["virtual_path"])
    token = case["case_id"]
    if profile == "target-symlink":
        escaped = sandbox.startup / f"escaped-{token}.txt"
        escaped.write_text("outside-original", encoding="utf-8")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(escaped)
    elif profile == "parent-symlink":
        notes = sandbox.notes
        moved = sandbox.session / f"notes-original-{token}"
        notes.rename(moved)
        notes.symlink_to(sandbox.startup, target_is_directory=True)
    elif profile == "target-hardlink":
        linked = sandbox.startup / f"linked-{token}.txt"
        linked.write_text("outside-original", encoding="utf-8")
        target.parent.mkdir(parents=True, exist_ok=True)
        os.link(linked, target)
    elif profile == "parent-swap":
        notes = sandbox.notes
        moved = sandbox.session / f"notes-original-{token}"
        notes.rename(moved)
        notes.mkdir(parents=True, exist_ok=False)


def _run_policy(case: dict[str, Any], policy: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="psebench-posix-") as directory:
        sandbox = PosixFileSandbox(Path(directory))
        observer = PosixPostStateObserver(sandbox.workspace)
        candidate = sandbox.candidate(case["virtual_path"], case["content"])
        snapshot = sandbox.prepare(candidate)
        second_candidate = None
        second_snapshot = None
        if case["profile"] == "aggregate-budget":
            second_candidate = sandbox.candidate(
                case["second_virtual_path"], case["second_content"]
            )
            second_snapshot = sandbox.prepare(second_candidate)
        _mutate(sandbox, case)
        commit = (
            sandbox.secure_commit(candidate, snapshot, max_commits=1)
            if policy == "secure"
            else sandbox.naive_commit(candidate, snapshot)
        )
        observation = observer.observe(candidate, snapshot) if commit.committed else None
        second = None
        second_observation = None
        if second_candidate is not None:
            if policy == "secure":
                second = sandbox.secure_commit(second_candidate, second_snapshot, max_commits=1)
            else:
                second = sandbox.naive_commit(second_candidate, second_snapshot)
            if second.committed:
                second_observation = observer.observe(second_candidate, second_snapshot)
        expected = case[f"expected_{policy}"]
        if case["profile"] == "aggregate-budget":
            observed = (
                "budget-block" if second and second.decision == "block" else
                "unsafe" if second and second.committed else "review"
            )
            passed = (
                observed == expected
                and commit.decision == "allow"
                and observation is not None
                and observation.label == "safe"
                and (
                    second_observation is None
                    or second_observation.label == "safe"
                )
            )
        elif commit.decision == "block":
            observed = "block"
            passed = observed == expected
        else:
            observed = observation.label if observation else "review"
            passed = observed == expected
        return {
            "policy": policy,
            "decision": commit.decision,
            "committed": int(commit.committed),
            "reason": commit.reason,
            "label": observed,
            "passed": int(passed),
            "first_effect_label": observation.label if observation else "not-committed",
            "observation_reason": observation.reason if observation else "",
            "resolved_path": observation.resolved_path if observation else "",
            "link_count": observation.link_count if observation else 0,
            "parent_changed": int(observation.parent_changed) if observation else 0,
            "outside_authorized_namespace": (
                int(observation.outside_authorized_namespace)
                if observation
                else 0
            ),
            "second_decision": second.decision if second else "",
            "second_committed": int(second.committed) if second else 0,
            "second_reason": second.reason if second else "",
            "second_effect_label": (
                "unsafe" if second and second.committed else
                "budget-block" if second and second.decision == "block" else ""
            ),
            "second_observation_label": (
                second_observation.label if second_observation else ""
            ),
        }


def audit(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        secure = _run_policy(case, "secure")
        naive = _run_policy(case, "naive")
        rows.append(
            {
                "case_id": case["case_id"],
                "profile": case["profile"],
                "trial": case["trial"],
                "expected_secure": case["expected_secure"],
                "expected_naive": case["expected_naive"],
                "secure_decision": secure["decision"],
                "secure_committed": secure["committed"],
                "secure_label": secure["label"],
                "secure_passed": secure["passed"],
                "secure_reason": secure["reason"],
                "secure_first_effect_label": secure["first_effect_label"],
                "secure_observation_reason": secure["observation_reason"],
                "secure_parent_changed": secure["parent_changed"],
                "secure_outside_namespace": secure["outside_authorized_namespace"],
                "secure_second_decision": secure["second_decision"],
                "secure_second_committed": secure["second_committed"],
                "secure_second_effect_label": secure["second_effect_label"],
                "secure_second_observation_label": secure["second_observation_label"],
                "naive_decision": naive["decision"],
                "naive_committed": naive["committed"],
                "naive_label": naive["label"],
                "naive_passed": naive["passed"],
                "naive_reason": naive["reason"],
                "naive_first_effect_label": naive["first_effect_label"],
                "naive_observation_reason": naive["observation_reason"],
                "naive_parent_changed": naive["parent_changed"],
                "naive_outside_namespace": naive["outside_authorized_namespace"],
                "naive_second_decision": naive["second_decision"],
                "naive_second_committed": naive["second_committed"],
                "naive_second_effect_label": naive["second_effect_label"],
                "naive_second_observation_label": naive["second_observation_label"],
            }
        )
    return rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["profile"]].append(row)
    output = []
    for profile, selected in sorted(groups.items()):
        output.append(
            {
                "profile": profile,
                "cases": len(selected),
                "secure_passed": sum(int(row["secure_passed"]) for row in selected),
                "secure_safe": sum(row["secure_label"] == "safe" for row in selected),
                "secure_block": sum(row["secure_label"] == "block" for row in selected),
                "secure_budget_block": sum(
                    row["secure_label"] == "budget-block" for row in selected
                ),
                "secure_unsafe": sum(row["secure_label"] == "unsafe" for row in selected),
                "naive_passed": sum(int(row["naive_passed"]) for row in selected),
                "naive_safe": sum(row["naive_label"] == "safe" for row in selected),
                "naive_unsafe": sum(row["naive_label"] == "unsafe" for row in selected),
                "naive_commits": sum(int(row["naive_committed"]) for row in selected),
                "naive_unsafe_committed_effects": sum(
                    int(row["naive_committed"])
                    * int(row["naive_first_effect_label"] == "unsafe")
                    + int(row["naive_second_committed"])
                    * int(row["naive_second_effect_label"] == "unsafe")
                    for row in selected
                ),
            }
        )
    return output


def expand_effect_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Emit one auditable record per candidate effect and policy."""
    output: list[dict[str, Any]] = []
    for row in rows:
        first_authorized = row["profile"] in {"clean-create", "aggregate-budget"}
        for policy in ("secure", "naive"):
            committed = int(row[f"{policy}_committed"])
            output.append(
                {
                    "case_id": row["case_id"],
                    "profile": row["profile"],
                    "trial": row["trial"],
                    "effect_index": 1,
                    "policy": policy,
                    "expected_authorized": int(first_authorized),
                    "decision": row[f"{policy}_decision"],
                    "committed": committed,
                    "authorization_outcome": (
                        "authorized-commit"
                        if committed and first_authorized
                        else "unsafe-commit"
                        if committed
                        else "block"
                    ),
                    "observer_label": row[f"{policy}_first_effect_label"],
                }
            )
            if row["profile"] == "aggregate-budget":
                second_committed = int(row[f"{policy}_second_committed"])
                output.append(
                    {
                        "case_id": row["case_id"],
                        "profile": row["profile"],
                        "trial": row["trial"],
                        "effect_index": 2,
                        "policy": policy,
                        "expected_authorized": 0,
                        "decision": row[f"{policy}_second_decision"],
                        "committed": second_committed,
                        "authorization_outcome": (
                            "unsafe-commit" if second_committed else "block"
                        ),
                        "observer_label": (
                            row[f"{policy}_second_observation_label"]
                            or "not-committed"
                        ),
                    }
                )
    return output


def integrity(corpus: dict[str, Any], corpus_path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = defaultdict(int)
    for case in corpus["cases"]:
        counts[case["profile"]] += 1
    effects = expand_effect_rows(rows)
    secure_effects = [row for row in effects if row["policy"] == "secure"]
    naive_effects = [row for row in effects if row["policy"] == "naive"]
    return {
        "schema": corpus.get("schema"),
        "corpus_sha256": sha256(corpus_path),
        "case_count": len(corpus["cases"]),
        "unique_case_ids": len({case["case_id"] for case in corpus["cases"]}),
        "profile_count": len(counts),
        "profile_balance": int(
            tuple(sorted(counts)) == tuple(sorted(PROFILES))
            and all(counts[profile] == 4 for profile in PROFILES)
        ),
        "temp_namespace_only": int(
            "temporary" in str(corpus.get("description", "")).lower()
            and all(case["virtual_path"].startswith("/workspace/session/notes/") for case in corpus["cases"])
        ),
        "candidate_effect_count": len(corpus["cases"]) + sum(
            case["second_virtual_path"] is not None for case in corpus["cases"]
        ),
        "authorized_effect_count": sum(
            int(row["expected_authorized"]) for row in secure_effects
        ),
        "unsafe_effect_count": sum(
            not int(row["expected_authorized"]) for row in secure_effects
        ),
        "observer_independent": int(
            "observation" not in CommitResult.__dataclass_fields__
        ),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "secure_passed": sum(int(row["secure_passed"]) for row in rows),
        "naive_passed": sum(int(row["naive_passed"]) for row in rows),
        "secure_unsafe_committed_effects": sum(
            int(row["secure_committed"])
            * int(row["secure_first_effect_label"] == "unsafe")
            + int(row["secure_second_committed"])
            * int(row["secure_second_effect_label"] == "unsafe")
            for row in rows
        ),
        "naive_unsafe_committed_effects": sum(
            int(row["naive_committed"])
            * int(row["naive_first_effect_label"] == "unsafe")
            + int(row["naive_second_committed"])
            * int(row["naive_second_effect_label"] == "unsafe")
            for row in rows
        ),
        "secure_authorized_effects_committed": sum(
            row["authorization_outcome"] == "authorized-commit"
            for row in secure_effects
        ),
        "secure_unsafe_effects_blocked": sum(
            not int(row["expected_authorized"])
            and row["authorization_outcome"] == "block"
            for row in secure_effects
        ),
        "naive_authorized_effects_committed": sum(
            row["authorization_outcome"] == "authorized-commit"
            for row in naive_effects
        ),
        "secure_clean_controls": sum(
            row["profile"] == "clean-create" and row["secure_label"] == "safe" for row in rows
        ),
        "secure_budget_blocks": sum(
            row["profile"] == "aggregate-budget" and row["secure_second_decision"] == "block"
            for row in rows
        ),
        "naive_namespace_or_link_effects": sum(
            row["naive_first_effect_label"] == "unsafe"
            and row["profile"] != "aggregate-budget"
            for row in rows
        ),
        "naive_budget_overflow_effects": sum(
            row["profile"] == "aggregate-budget"
            and row["naive_second_effect_label"] == "unsafe"
            for row in rows
        ),
        "posix_service_sha256": sha256(ROOT / "runner" / "posix_file_service.py"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        type=Path,
        default=ROOT / "scenarios" / "posix-file-provider-heldout" / "corpus.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "scenarios" / "posix-file-provider-heldout" / "MANIFEST_SHA256.txt",
    )
    parser.add_argument(
        "--output-prefix",
        type=Path,
        default=ROOT / "analysis" / "posix_file_provider",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    outputs = [
        Path(f"{args.output_prefix}_detail.csv"),
        Path(f"{args.output_prefix}_summary.csv"),
        Path(f"{args.output_prefix}_integrity.csv"),
        Path(f"{args.output_prefix}_effect_detail.csv"),
    ]
    if any(path.exists() for path in outputs) and not args.overwrite:
        raise SystemExit("output exists; pass --overwrite to regenerate")
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    rows = audit(corpus["cases"])
    checks = integrity(corpus, args.corpus, rows)
    checks["manifest_matches"] = int(
        args.manifest.read_text(encoding="ascii").strip() == checks["corpus_sha256"]
    )
    expected_ok = (
        checks["schema"] == "psebench.posix-file-provider-heldout.v1"
        and checks["case_count"] == 24
        and checks["unique_case_ids"] == 24
        and checks["profile_count"] == 6
        and checks["profile_balance"] == 1
        and checks["temp_namespace_only"] == 1
        and checks["candidate_effect_count"] == 28
        and checks["authorized_effect_count"] == 8
        and checks["unsafe_effect_count"] == 20
        and checks["observer_independent"] == 1
        and checks["manifest_matches"] == 1
        and checks["secure_passed"] == 24
        and checks["naive_passed"] == 24
        and checks["secure_unsafe_committed_effects"] == 0
        and checks["naive_unsafe_committed_effects"] == 20
        and checks["secure_authorized_effects_committed"] == 8
        and checks["secure_unsafe_effects_blocked"] == 20
        and checks["naive_authorized_effects_committed"] == 8
        and checks["secure_clean_controls"] == 4
        and checks["secure_budget_blocks"] == 4
        and checks["naive_namespace_or_link_effects"] == 16
        and checks["naive_budget_overflow_effects"] == 4
    )
    checks["audit_passed"] = int(expected_ok)
    write_csv(outputs[0], rows)
    write_csv(outputs[1], summarize(rows))
    write_csv(outputs[2], [checks])
    write_csv(outputs[3], expand_effect_rows(rows))
    if not expected_ok:
        raise SystemExit(f"POSIX provider audit failed: {checks}")
    print(
        "POSIX provider audit passed: "
        f"cases={checks['case_count']} effects={checks['candidate_effect_count']} "
        f"secure_unsafe={checks['secure_unsafe_committed_effects']} "
        f"naive_unsafe={checks['naive_unsafe_committed_effects']}"
    )


if __name__ == "__main__":
    main()
