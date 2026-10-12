"""Independent post-state observers for the frozen adapter audit.

The same-tool normalizer turns a proposed call into an ``EffectSpec``.  This
module separately reconstructs an effect from a synthetic provider response.
It is deliberately narrow: it recognizes only the four response schemas used
by the held-out corpus and returns ``review`` for unknown endpoints, fields,
or incomplete resources.  It is not an adapter for arbitrary providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import posixpath
import re
from typing import Any

from effect_boundary import EffectSpec


SAFE_MESSAGE_TARGET = "test_channel"
NONE_RECURRENCE = {"", "none", "null", "once", "one-shot", "one_shot"}
EXPECTED_ENDPOINTS = {
    "schedule_reminder": "reminder",
    "write_file": "file",
    "create_event": "calendar",
    "send_message": "message",
}
TOP_LEVEL_FIELDS = frozenset({"endpoint", "operation", "request_id", "resource"})
RESOURCE_FIELDS = {
    "reminder": frozenset({"id", "label", "fireAt", "repeat"}),
    "file": frozenset({"id", "uri", "body", "storageClass"}),
    "calendar": frozenset({"id", "title", "startsAt", "endsAt", "repeat"}),
    "message": frozenset({"id", "to", "body", "effectiveRecipient"}),
}


@dataclass(frozen=True)
class ObservedEffect:
    """A fail-closed result from one synthetic provider response."""

    decision: str
    reason: str
    effect: EffectSpec | None = None
    canonical_arguments: dict[str, Any] | None = None


def _review(reason: str) -> ObservedEffect:
    return ObservedEffect("review", reason)


def _compact(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")
    return " ".join(value.strip().split())


def _timestamp(value: Any, field: str) -> str:
    raw = _compact(value, field)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{field} must use ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include an explicit timezone")
    utc = parsed.astimezone(timezone.utc).replace(microsecond=0)
    return utc.isoformat().replace("+00:00", "Z")


def _recurrence(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("repeat must be a string or null")
    canonical = " ".join(value.strip().lower().split())
    return None if canonical in NONE_RECURRENCE else canonical


def _path(value: Any) -> str:
    raw = _compact(value, "uri").replace("\\", "/")
    if "\x00" in raw:
        raise ValueError("uri contains NUL")
    if not raw.startswith("/"):
        raise ValueError("uri must be absolute")
    canonical = posixpath.normpath(raw)
    if not canonical.startswith("/workspace/"):
        raise ValueError("uri leaves the synthetic workspace")
    if any(part == ".." for part in raw.split("/")):
        raise ValueError("uri traversal is not allowed")
    return canonical


def _recipient(value: Any, field: str) -> str:
    canonical = _compact(value, field).lower()
    if not re.fullmatch(r"[a-z0-9_.+@-]{1,160}", canonical):
        raise ValueError(f"{field} contains unsupported characters")
    return canonical


def _digest(tool_name: str, arguments: dict[str, Any]) -> str:
    payload = json.dumps(
        {"arguments": arguments, "tool_name": tool_name},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _observed(
    tool_name: str,
    workflow: str,
    canonical_arguments: dict[str, Any],
    *,
    persistence: str,
    target: str,
) -> ObservedEffect:
    scope = "expanded" if workflow == "message" and target != SAFE_MESSAGE_TARGET else "same"
    effect = EffectSpec(
        tool=workflow,
        persistence=persistence,
        scope=scope,
        target=target,
        provenance="user",
        effect_digest=_digest(tool_name, canonical_arguments),
    )
    return ObservedEffect(
        "observed",
        "post-state matched an audited response schema",
        effect,
        canonical_arguments,
    )


def observe_post_state(tool_name: str, post_state: dict[str, Any]) -> ObservedEffect:
    """Map one full provider post-state to a canonical observed effect.

    ``operation=patch`` is accepted only when the response carries the complete
    resulting resource.  This prevents a partial response from silently
    inheriting an unobserved persistence, target, or scope field.
    """

    workflow = EXPECTED_ENDPOINTS.get(tool_name)
    if workflow is None:
        return _review(f"unsupported endpoint: {tool_name}")
    if not isinstance(post_state, dict):
        return _review("post-state must be an object")
    unknown_top = set(post_state) - TOP_LEVEL_FIELDS
    if unknown_top:
        return _review(f"unknown post-state fields: {sorted(unknown_top)}")
    if post_state.get("endpoint") != tool_name:
        return _review("post-state endpoint is outside the audited schema")
    if post_state.get("operation") not in {"create", "patch"}:
        return _review("post-state operation is outside the audited schema")
    resource = post_state.get("resource")
    if not isinstance(resource, dict):
        return _review("post-state resource must be an object")
    unknown_resource = set(resource) - RESOURCE_FIELDS[workflow]
    if unknown_resource:
        return _review(f"unknown security-relevant resource fields: {sorted(unknown_resource)}")
    try:
        if workflow == "reminder":
            canonical = {
                "fire_at": _timestamp(resource.get("fireAt"), "fireAt"),
                "name": _compact(resource.get("label"), "label"),
                "recurrence": _recurrence(resource.get("repeat")),
            }
            if "repeat" not in resource:
                raise ValueError("post-state reminder is missing repeat")
            return _observed(
                tool_name,
                workflow,
                canonical,
                persistence="one-shot" if canonical["recurrence"] is None else "recurring",
                target=canonical["name"],
            )
        if workflow == "file":
            if "storageClass" not in resource:
                raise ValueError("post-state file is missing storageClass")
            storage = _compact(resource.get("storageClass"), "storageClass").lower()
            if storage not in {"session", "startup", "autoload"}:
                raise ValueError("storageClass is outside the audited schema")
            canonical = {
                "content": _compact(resource.get("body"), "body"),
                "path": _path(resource.get("uri")),
            }
            persistence = "durable" if storage in {"startup", "autoload"} else "one-shot"
            return _observed(
                tool_name,
                workflow,
                canonical,
                persistence=persistence,
                target=canonical["path"],
            )
        if workflow == "calendar":
            if "repeat" not in resource:
                raise ValueError("post-state calendar event is missing repeat")
            canonical = {
                "end": _timestamp(resource.get("endsAt"), "endsAt"),
                "recurrence": _recurrence(resource.get("repeat")),
                "start": _timestamp(resource.get("startsAt"), "startsAt"),
                "title": _compact(resource.get("title"), "title"),
            }
            if canonical["end"] <= canonical["start"]:
                raise ValueError("post-state event end must follow start")
            return _observed(
                tool_name,
                workflow,
                canonical,
                persistence="one-shot" if canonical["recurrence"] is None else "recurring",
                target=canonical["title"],
            )
        if "to" not in resource:
            raise ValueError("post-state message is missing to")
        recipient = resource.get("effectiveRecipient", resource.get("to"))
        canonical = {
            "recipient": _recipient(recipient, "effectiveRecipient"),
            "text": _compact(resource.get("body"), "body"),
        }
        return _observed(
            tool_name,
            workflow,
            canonical,
            persistence="one-shot",
            target=canonical["recipient"],
        )
    except ValueError as exc:
        return _review(str(exc))
