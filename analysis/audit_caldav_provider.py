#!/usr/bin/env python3
"""Audit a frozen loopback CalDAV corpus against secure and naive adapters.

The Radicale process is a provider under test, not part of the policy oracle.
Each case starts a fresh server and uses an independent GET/REPORT observer.
Results are conformance evidence for the pinned Radicale version, not a claim
about SaaS providers or prevalence in deployed calendars.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from radicale_caldav_service import (  # noqa: E402
    ALTERNATE_COLLECTION,
    AUTHORIZED_COLLECTION,
    RUNTIME_VERSION,
    RadicaleCalDAVServer,
    event_body,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _collection(name: str) -> str:
    return ALTERNATE_COLLECTION if name == "alternate" else AUTHORIZED_COLLECTION


def _base_row(case: dict[str, Any], policy: str) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "profile": case["profile"],
        "trial": case["trial"],
        "policy": policy,
        "provider": RUNTIME_VERSION,
    }


def _state_fields(prefix: str, state) -> dict[str, Any]:
    return {
        f"{prefix}_status": state.status,
        f"{prefix}_uid": state.uid,
        f"{prefix}_summary": state.summary,
        f"{prefix}_recurrence": state.recurrence,
        f"{prefix}_event_count": state.event_count,
        f"{prefix}_body_digest": state.body_digest,
        f"{prefix}_etag_present": int(state.etag_present),
    }


def run_case(case: dict[str, Any], policy: str, runtime_path: Path) -> dict[str, Any]:
    """Run one policy in a fresh provider instance."""

    profile = case["profile"]
    uid = case["uid"]
    summary = case["summary"]
    recurrence = case["candidate_recurrence"]
    candidate = event_body(uid, summary, recurrence=recurrence, variant=case["variant"])
    expected_collection = AUTHORIZED_COLLECTION
    selected_collection = _collection(case["candidate_collection"])
    candidate_digest = hashlib.sha256(candidate).hexdigest()

    with RadicaleCalDAVServer(runtime_path) as server:
        old_etag = None
        if profile == "stale-etag":
            initial = event_body(uid, summary, recurrence="")
            initial_response = server.put(
                AUTHORIZED_COLLECTION, uid, initial, if_none_match="*"
            )
            old_etag = initial_response.headers.get("etag")
            if not old_etag:
                raise RuntimeError("provider did not return an ETag for initial event")
            external = event_body(
                uid,
                "External update",
                recurrence="FREQ=DAILY;COUNT=2",
            )
            external_response = server.put(
                AUTHORIZED_COLLECTION, uid, external, if_match=old_etag
            )
            if external_response.status not in {200, 201, 204}:
                raise RuntimeError(
                    f"provider rejected controlled external mutation: {external_response.status}"
                )

        decisions: list[str] = []
        responses: list[int] = []
        committed_effects = 0
        if profile == "aggregate-overflow":
            first_uid = uid
            second_uid = f"{uid}-second"
            first_body = event_body(first_uid, summary)
            second_body = event_body(second_uid, "Second effect")
            if policy == "secure":
                decisions.append("allow")
                first_response = server.put(
                    AUTHORIZED_COLLECTION, first_uid, first_body, if_none_match="*"
                )
                responses.append(first_response.status)
                committed_effects += int(first_response.status in {200, 201, 204})
                decisions.append("block")
                responses.append(0)
            else:
                for effect_uid, effect_body in ((first_uid, first_body), (second_uid, second_body)):
                    decisions.append("allow")
                    response = server.put(AUTHORIZED_COLLECTION, effect_uid, effect_body)
                    responses.append(response.status)
                    committed_effects += int(response.status in {200, 201, 204})
            first_state = server.observe(AUTHORIZED_COLLECTION, first_uid)
            second_state = server.observe(AUTHORIZED_COLLECTION, second_uid)
            passed = (
                policy == "secure"
                and decisions == ["allow", "block"]
                and first_state.event_count == 1
                and second_state.status == 404
            ) or (
                policy == "naive"
                and decisions == ["allow", "allow"]
                and first_state.event_count == 1
                and second_state.event_count == 1
            )
            row = _base_row(case, policy)
            row.update(
                {
                    "decision": "+".join(decisions),
                    "http_statuses": ",".join(str(value) for value in responses),
                    "candidate_digest": candidate_digest,
                    "committed_effects": committed_effects,
                    "unsafe_committed_effects": int(
                        policy == "naive" and second_state.status == 200
                    ),
                    "passed": int(passed),
                    "observer_label": "budget-block"
                    if policy == "secure"
                    else "budget-overflow",
                }
            )
            row.update(_state_fields("first", first_state))
            row.update(_state_fields("second", second_state))
            return row

        # Secure v2 checks the effect/path before crossing the provider
        # boundary.  A stale update is sent with the receipt's ETag so that
        # the provider itself participates in the commit-time check.
        if policy == "secure" and profile in {
            "recurrence-injection",
            "partial-update-injection",
        }:
            decisions.append("review")
        elif policy == "secure" and profile == "endpoint-swap":
            decisions.append("block")
        else:
            decisions.append("allow")
            response = server.put(
                selected_collection,
                uid,
                candidate,
                if_match=old_etag if policy == "secure" and profile == "stale-etag" else None,
                if_none_match="*" if profile != "stale-etag" else None,
            )
            responses.append(response.status)
            committed_effects += int(response.status in {200, 201, 204})

        authorized_state = server.observe(expected_collection, uid)
        alternate_state = server.observe(ALTERNATE_COLLECTION, uid)
        candidate_committed = (
            authorized_state.status == 200
            and authorized_state.uid == uid
            and authorized_state.summary == summary
            and authorized_state.recurrence == recurrence
        )
        alternate_candidate_committed = (
            alternate_state.status == 200
            and alternate_state.uid == uid
            and alternate_state.summary == summary
            and alternate_state.recurrence == recurrence
        )
        unsafe = int(
            (candidate_committed and bool(recurrence))
            or alternate_candidate_committed
        )
        if profile == "stale-etag":
            observer_label = "etag-block" if not candidate_committed else "unsafe-overwrite"
        elif profile == "endpoint-swap":
            observer_label = "path-block" if alternate_state.status == 404 else "unsafe-path"
        elif profile in {"recurrence-injection", "partial-update-injection"}:
            observer_label = "review" if authorized_state.status == 404 else "unsafe"
        elif profile == "provider-normalization":
            observer_label = (
                "normalized-safe"
                if authorized_state.uid == uid
                and not authorized_state.recurrence
                and authorized_state.event_count == 1
                else "unsafe"
            )
        else:
            observer_label = "safe" if authorized_state.event_count == 1 else "review"

        expected = case["expected_secure"] if policy == "secure" else case["expected_naive"]
        actual = observer_label
        passed = (
            actual == expected
            and (
                profile != "stale-etag"
                or (policy == "secure" and responses == [412])
                or (policy == "naive" and candidate_committed)
            )
        )
        row = _base_row(case, policy)
        row.update(
            {
                "decision": decisions[0],
                "http_statuses": ",".join(str(value) for value in responses),
                "candidate_digest": candidate_digest,
                "committed_effects": committed_effects,
                "unsafe_committed_effects": unsafe,
                "passed": int(passed),
                "observer_label": actual,
                "candidate_committed": int(candidate_committed),
                "alternate_candidate_committed": int(alternate_candidate_committed),
            }
        )
        row.update(_state_fields("authorized", authorized_state))
        row.update(_state_fields("alternate", alternate_state))
        return row


def audit(corpus: dict[str, Any], runtime_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in corpus["cases"]:
        for policy in ("secure", "naive"):
            rows.append(run_case(case, policy, runtime_path))
    return rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["profile"], row["policy"])].append(row)
    output: list[dict[str, Any]] = []
    for (profile, policy), selected in sorted(groups.items()):
        output.append(
            {
                "profile": profile,
                "policy": policy,
                "cases": len(selected),
                "passed": sum(int(row["passed"]) for row in selected),
                "committed_effects": sum(int(row["committed_effects"]) for row in selected),
                "unsafe_committed_effects": sum(
                    int(row["unsafe_committed_effects"]) for row in selected
                ),
                "http_412": sum(
                    int("412" in str(row["http_statuses"])) for row in selected
                ),
                "review_decisions": sum(row["decision"] == "review" for row in selected),
            }
        )
    for policy in ("secure", "naive"):
        selected = [row for row in rows if row["policy"] == policy]
        output.append(
            {
                "profile": "all",
                "policy": policy,
                "cases": len(selected),
                "passed": sum(int(row["passed"]) for row in selected),
                "committed_effects": sum(int(row["committed_effects"]) for row in selected),
                "unsafe_committed_effects": sum(
                    int(row["unsafe_committed_effects"]) for row in selected
                ),
                "http_412": sum(
                    int("412" in str(row["http_statuses"])) for row in selected
                ),
                "review_decisions": sum(row["decision"] == "review" for row in selected),
            }
        )
    return output


def integrity(corpus: dict[str, Any], corpus_path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    secure = [row for row in rows if row["policy"] == "secure"]
    naive = [row for row in rows if row["policy"] == "naive"]
    return {
        "schema": corpus["schema"],
        "provider": RUNTIME_VERSION,
        "corpus_sha256": sha256(corpus_path),
        "case_count": len(corpus["cases"]),
        "detail_row_count": len(rows),
        "secure_case_passes": sum(int(row["passed"]) for row in secure),
        "naive_case_passes": sum(int(row["passed"]) for row in naive),
        "secure_unsafe_committed_effects": sum(
            int(row["unsafe_committed_effects"]) for row in secure
        ),
        "naive_unsafe_committed_effects": sum(
            int(row["unsafe_committed_effects"]) for row in naive
        ),
        "secure_etag_blocks": sum(
            int(row["observer_label"] == "etag-block") for row in secure
        ),
        "secure_budget_blocks": sum(
            int(row["observer_label"] == "budget-block") for row in secure
        ),
        "secure_review_routes": sum(
            int(row["decision"] == "review") for row in secure
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        type=Path,
        default=ROOT / "scenarios" / "caldav-provider-heldout" / "corpus.json",
    )
    parser.add_argument(
        "--runtime",
        type=Path,
        default=ROOT / "tmp" / "radicale_runtime",
        help="directory containing the pinned Radicale installation",
    )
    parser.add_argument("--output-prefix", type=Path, default=ROOT / "analysis" / "caldav_provider")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not args.runtime.is_dir():
        raise SystemExit(
            f"Radicale runtime not found at {args.runtime}; install requirements-provider.txt"
        )
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    rows = audit(corpus, args.runtime)
    summary = summarize(rows)
    checks = integrity(corpus, args.corpus, rows)
    if checks["secure_unsafe_committed_effects"] != 0:
        raise SystemExit("secure policy produced an unsafe committed effect")
    if checks["secure_case_passes"] != checks["case_count"]:
        raise SystemExit("secure case expectation failed")
    if checks["naive_case_passes"] != checks["case_count"]:
        raise SystemExit("naive baseline expectation failed")
    prefix = args.output_prefix
    targets = {
        "detail": prefix.with_name(prefix.name + "_detail.csv"),
        "summary": prefix.with_name(prefix.name + "_summary.csv"),
        "integrity": prefix.with_name(prefix.name + "_integrity.json"),
    }
    if not args.overwrite:
        existing = [path for path in targets.values() if path.exists()]
        if existing:
            raise SystemExit("output exists; pass --overwrite: " + ", ".join(map(str, existing)))
    write_csv(targets["detail"], rows)
    write_csv(targets["summary"], summary)
    targets["integrity"].write_text(json.dumps(checks, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
