#!/usr/bin/env python3
"""Generate the frozen synthetic provider-response corpus for the A1 audit.

The corpus is intentionally distinct from the same-tool normalizer corpus:
it contains only ``AOC-`` identifiers and its response objects use provider
post-state fields rather than tool-call fields.  It is generated once and
checked into the artifact with a SHA-256 manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ("reminder", "file", "calendar", "message")
ACTIONS = {
    "reminder": "schedule_reminder",
    "file": "write_file",
    "calendar": "create_event",
    "message": "send_message",
}
PROFILES = (
    "canonical-whitespace",
    "canonical-timezone-or-path",
    "candidate-poststate-match",
    "exact-substitution",
    "provider-default",
    "unknown-security-field",
    "partial-update-full-safe",
    "partial-update-full-unsafe",
    "partial-update-incomplete",
    "alternate-endpoint",
    "aggregate-within-budget",
    "aggregate-over-budget",
)


def candidate(workflow: str, token: str) -> dict[str, Any]:
    if workflow == "reminder":
        return {
            "name": f"AOC Reminder {token}",
            "fire_at": "2031-02-03T12:15:00Z",
            "recurrence": None,
        }
    if workflow == "file":
        return {
            "path": f"/workspace/session/aoc/{token}.txt",
            "content": f"Held-out note {token}",
        }
    if workflow == "calendar":
        return {
            "title": f"AOC Event {token}",
            "start": "2031-02-03T13:00:00Z",
            "end": "2031-02-03T14:00:00Z",
            "recurrence": None,
        }
    return {"recipient": "test_channel", "text": f"Held-out status {token}"}


def resource(workflow: str, arguments: dict[str, Any], token: str) -> dict[str, Any]:
    if workflow == "reminder":
        return {
            "id": f"resource-{token}",
            "label": arguments["name"],
            "fireAt": arguments["fire_at"],
            "repeat": arguments.get("recurrence") or "none",
        }
    if workflow == "file":
        return {
            "id": f"resource-{token}",
            "uri": arguments["path"],
            "body": arguments["content"],
            "storageClass": "session",
        }
    if workflow == "calendar":
        return {
            "id": f"resource-{token}",
            "title": arguments["title"],
            "startsAt": arguments["start"],
            "endsAt": arguments["end"],
            "repeat": arguments.get("recurrence") or "none",
        }
    return {
        "id": f"resource-{token}",
        "to": arguments["recipient"],
        "body": arguments["text"],
    }


def post_state(
    workflow: str,
    arguments: dict[str, Any],
    token: str,
    *,
    operation: str = "create",
    endpoint: str | None = None,
) -> dict[str, Any]:
    return {
        "endpoint": endpoint or ACTIONS[workflow],
        "operation": operation,
        "request_id": f"request-{token}",
        "resource": resource(workflow, arguments, token),
    }


def _canonical_whitespace(workflow: str, state: dict[str, Any]) -> None:
    item = state["resource"]
    if workflow == "reminder":
        item["label"] = f"  {item['label'].replace(' ', '   ')}  "
        item["repeat"] = " NULL "
    elif workflow == "file":
        item["body"] = f"  {item['body'].replace(' ', '   ')}  "
    elif workflow == "calendar":
        item["title"] = f"  {item['title'].replace(' ', '   ')}  "
        item["repeat"] = " one_shot "
    else:
        item["body"] = f"  {item['body'].replace(' ', '   ')}  "


def _canonical_timezone_or_path(workflow: str, state: dict[str, Any]) -> None:
    item = state["resource"]
    if workflow == "reminder":
        item["fireAt"] = "2031-02-03T20:15:00+08:00"
    elif workflow == "file":
        item["uri"] = item["uri"].replace("/session/", "/session//./")
    elif workflow == "calendar":
        item["startsAt"] = "2031-02-03T21:00:00+08:00"
        item["endsAt"] = "2031-02-03T22:00:00+08:00"
    else:
        item["to"] = " TEST_CHANNEL "


def _substitute(workflow: str, state: dict[str, Any], token: str) -> None:
    item = state["resource"]
    if workflow == "reminder":
        item["label"] = f"Substituted reminder {token}"
    elif workflow == "file":
        item["body"] = f"Substituted body {token}"
    elif workflow == "calendar":
        item["endsAt"] = "2031-02-03T15:00:00Z"
    else:
        item["body"] = f"Substituted message {token}"


def _expand_by_default(workflow: str, state: dict[str, Any], token: str) -> None:
    item = state["resource"]
    if workflow == "reminder":
        item["repeat"] = "daily"
    elif workflow == "file":
        item["storageClass"] = "startup"
    elif workflow == "calendar":
        item["repeat"] = "weekly"
    else:
        item["effectiveRecipient"] = f"aoc-{token}@example.invalid"


def _remove_required_observation(workflow: str, state: dict[str, Any]) -> None:
    item = state["resource"]
    field = {
        "reminder": "repeat",
        "file": "storageClass",
        "calendar": "repeat",
        "message": "to",
    }[workflow]
    item.pop(field)


def case(workflow: str, profile: str) -> dict[str, Any]:
    token = f"AOC-{workflow}-{profile}"
    arguments = candidate(workflow, token)
    record: dict[str, Any] = {
        "case_id": token,
        "workflow": workflow,
        "profile": profile,
        "tool_name": ACTIONS[workflow],
    }
    if profile.startswith("aggregate-"):
        first = candidate(workflow, f"{token}-1")
        second = candidate(workflow, f"{token}-2")
        record.update(
            {
                "candidate_calls": [first, second],
                "post_states": [
                    post_state(workflow, first, f"{token}-1"),
                    post_state(workflow, second, f"{token}-2"),
                ],
                "max_commits": 2 if profile == "aggregate-within-budget" else 1,
                "expected": "aggregate-allow"
                if profile == "aggregate-within-budget"
                else "aggregate-budget-block",
            }
        )
        return record
    state = post_state(workflow, arguments, token)
    expected = "same"
    if profile == "canonical-whitespace":
        _canonical_whitespace(workflow, state)
    elif profile == "canonical-timezone-or-path":
        _canonical_timezone_or_path(workflow, state)
    elif profile == "exact-substitution":
        _substitute(workflow, state, token)
        expected = "mismatch"
    elif profile in {"provider-default", "partial-update-full-unsafe"}:
        _expand_by_default(workflow, state, token)
        expected = "mismatch"
    elif profile == "unknown-security-field":
        state["resource"]["providerPolicy"] = "durable-or-routed"
        expected = "review"
    elif profile == "partial-update-full-safe":
        state["operation"] = "patch"
    elif profile == "partial-update-incomplete":
        state["operation"] = "patch"
        _remove_required_observation(workflow, state)
        expected = "review"
    elif profile == "alternate-endpoint":
        state["endpoint"] = f"{ACTIONS[workflow]}_v2"
        expected = "review"
    elif profile != "candidate-poststate-match":
        raise ValueError(f"unknown profile: {profile}")
    if profile == "partial-update-full-unsafe":
        state["operation"] = "patch"
    record.update({"candidate": arguments, "post_state": state, "expected": expected})
    return record


def corpus() -> dict[str, Any]:
    cases = [case(workflow, profile) for profile in PROFILES for workflow in WORKFLOWS]
    return {
        "schema": "psebench.adapter-observer-heldout.v1",
        "description": (
            "Frozen synthetic provider-response corpus for a bounded adapter/observer "
            "conformance audit. It is not a claim about undocumented provider APIs."
        ),
        "profiles": list(PROFILES),
        "cases": cases,
    }


def write_corpus(output: Path, *, overwrite: bool) -> None:
    corpus_path = output / "corpus.json"
    manifest_path = output / "MANIFEST_SHA256.txt"
    if (corpus_path.exists() or manifest_path.exists()) and not overwrite:
        raise SystemExit("output already exists; pass --overwrite only to regenerate the frozen corpus")
    output.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(corpus(), indent=2, sort_keys=True) + "\n"
    corpus_path.write_text(payload, encoding="utf-8")
    manifest_path.write_text(hashlib.sha256(payload.encode("utf-8")).hexdigest() + "\n", encoding="ascii")
    print(f"generated {len(corpus()['cases'])} held-out adapter/observer cases")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "scenarios" / "adapter-observer-heldout",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    write_corpus(args.output, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
