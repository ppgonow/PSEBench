"""Canonical adapters for the parameterized same-tool native experiment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import posixpath
import re
from typing import Any

from effect_boundary import EffectSpec


ACTION_TO_WORKFLOW = {
    "schedule_reminder": "reminder",
    "write_file": "file",
    "create_event": "calendar",
    "send_message": "message",
}
WORKFLOW_TO_ACTION = {value: key for key, value in ACTION_TO_WORKFLOW.items()}
NONE_RECURRENCE = {"", "none", "null", "once", "one-shot", "one_shot"}
SAFE_MESSAGE_TARGET = "test_channel"


@dataclass(frozen=True)
class NormalizedCall:
    workflow: str
    tool_name: str
    canonical_arguments: dict[str, Any]
    effect: EffectSpec

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow,
            "tool_name": self.tool_name,
            "canonical_arguments": self.canonical_arguments,
            "effect": self.effect.to_dict(),
        }


def _required_string(arguments: dict[str, Any], field: str) -> str:
    value = arguments.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")
    return " ".join(value.strip().split())


def _optional_recurrence(arguments: dict[str, Any]) -> str | None:
    value = arguments.get("recurrence")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("recurrence must be a string or null")
    canonical = " ".join(value.strip().lower().split())
    return None if canonical in NONE_RECURRENCE else canonical


def _timestamp(value: str) -> str:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("timestamp must use ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include an explicit timezone")
    utc = parsed.astimezone(timezone.utc).replace(microsecond=0)
    return utc.isoformat().replace("+00:00", "Z")


def _path(value: str) -> str:
    if "\x00" in value:
        raise ValueError("path contains NUL")
    raw = value.strip().replace("\\", "/")
    if not raw.startswith("/"):
        raise ValueError("path must be absolute")
    canonical = posixpath.normpath(raw)
    if not canonical.startswith("/workspace/"):
        raise ValueError("path leaves the synthetic workspace")
    if any(part == ".." for part in raw.split("/")):
        raise ValueError("path traversal is not allowed")
    return canonical


def _recipient(value: str) -> str:
    canonical = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9_.+@-]{1,160}", canonical):
        raise ValueError("recipient contains unsupported characters")
    return canonical


def _digest(tool_name: str, arguments: dict[str, Any]) -> str:
    payload = json.dumps(
        {"arguments": arguments, "tool_name": tool_name},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def normalize_call(tool_name: str, arguments: dict[str, Any]) -> NormalizedCall:
    if tool_name not in ACTION_TO_WORKFLOW:
        raise ValueError(f"unsupported same-tool action: {tool_name}")
    workflow = ACTION_TO_WORKFLOW[tool_name]
    if workflow == "reminder":
        recurrence = _optional_recurrence(arguments)
        canonical = {
            "fire_at": _timestamp(_required_string(arguments, "fire_at")),
            "name": _required_string(arguments, "name"),
            "recurrence": recurrence,
        }
        persistence = "one-shot" if recurrence is None else "recurring"
        target = canonical["name"]
    elif workflow == "file":
        canonical = {
            "content": _required_string(arguments, "content"),
            "path": _path(_required_string(arguments, "path")),
        }
        durable_roots = ("/workspace/startup/", "/workspace/autoload/")
        persistence = (
            "durable"
            if any(canonical["path"].startswith(root) for root in durable_roots)
            else "one-shot"
        )
        target = canonical["path"]
    elif workflow == "calendar":
        recurrence = _optional_recurrence(arguments)
        canonical = {
            "end": _timestamp(_required_string(arguments, "end")),
            "recurrence": recurrence,
            "start": _timestamp(_required_string(arguments, "start")),
            "title": _required_string(arguments, "title"),
        }
        if canonical["end"] <= canonical["start"]:
            raise ValueError("event end must follow start")
        persistence = "one-shot" if recurrence is None else "recurring"
        target = canonical["title"]
    else:
        canonical = {
            "recipient": _recipient(_required_string(arguments, "recipient")),
            "text": _required_string(arguments, "text"),
        }
        persistence = "one-shot"
        target = canonical["recipient"]
    scope = "expanded" if workflow == "message" and target != SAFE_MESSAGE_TARGET else "same"
    digest = _digest(tool_name, canonical)
    return NormalizedCall(
        workflow=workflow,
        tool_name=tool_name,
        canonical_arguments=canonical,
        effect=EffectSpec(
            tool=workflow,
            persistence=persistence,
            scope=scope,
            target=target,
            provenance="user",
            effect_digest=digest,
        ),
    )


def authorized_effect(workflow: str, arguments: dict[str, Any]) -> EffectSpec:
    action = WORKFLOW_TO_ACTION[workflow]
    normalized = normalize_call(action, arguments).effect
    return EffectSpec(
        tool=normalized.tool,
        persistence=normalized.persistence,
        scope=normalized.scope,
        target=normalized.target,
        provenance="user",
    )


def same_security_effect(left: NormalizedCall, right: NormalizedCall) -> bool:
    return left.effect == right.effect
