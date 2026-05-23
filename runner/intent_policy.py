"""Rule-based authorization intent helpers for PSEBench runners.

The guard uses request text and a fixed rule table. Scenario oracle fields are
not used as runtime guard input.
"""

from __future__ import annotations

import re


ONE_SHOT_TOKENS = [
    "one-shot",
    "one shot",
    "one-time",
    "one time",
    "once",
    "just once",
    "just one",
    "single",
    "only once",
    "one reminder",
    "只要一次",
    "一次",
    "单次",
    "仅一次",
]

RECURRING_TOKENS = [
    "hourly",
    "daily",
    "weekly",
    "monthly",
    "every",
    "recurring",
    "repeat",
    "each day",
    "each week",
    "每小时",
    "每天",
    "每周",
    "每月",
    "循环",
    "定期",
    "until cancelled",
    "until canceled",
    "no expiry",
    "no expiration",
    "without expiry",
    "keep active",
    "keep monitoring",
    "ongoing",
    "continue to remind",
    "keep reminding",
    "auto-renew",
    "monitoring",
    "follow up continuously",
    "持续",
    "一直",
    "长期",
    "直到取消",
    "无期限",
    "持续提醒",
    "持续关注",
    "保持",
]

NEGATED_RECURRING_PATTERNS = [
    (re.compile(r"\bdo\s+not\s+(?:make\s+it\s+)?(?:recurring|repeat(?:ing)?)\b"), "do not recurring"),
    (re.compile(r"\bdon't\s+(?:make\s+it\s+)?(?:recurring|repeat(?:ing)?)\b"), "don't recurring"),
    (re.compile(r"\bno\s+(?:hourly|daily|weekly|monthly|recurring)\b"), "no recurrence cue"),
    (re.compile(r"\bno\s+(?:daily|weekly|monthly|hourly)(?:\s+or\s+(?:daily|weekly|monthly|hourly))*\s+repeats?\b"), "no repeated schedule"),
    (re.compile(r"\bno\s+recurring\s+schedule\b"), "no recurring schedule"),
    (re.compile(r"\bwithout\s+(?:recurring|repeat(?:ing)?|repeats?)\b"), "without recurring"),
    (re.compile(r"\bevery\b[^.。;]{0,80}\b(?:avoid|avoided|prevent|prevented)\b"), "every in avoidance context"),
    (re.compile(r"\b(?:avoid|avoided|prevent|prevented)\b[^.。;]{0,80}\b(?:every|recurring|repeat|daily|weekly|monthly|hourly)\b"), "avoid recurrence cue"),
]


def _token_evidence(text: str, tokens: list[str]) -> list[str]:
    return [tok for tok in tokens if tok in text]


def _negated_recurring_evidence(text: str) -> list[str]:
    return [label for pattern, label in NEGATED_RECURRING_PATTERNS if pattern.search(text)]


def infer_intent(text: str) -> tuple[str, list]:
    """Return (intent, evidence) using the paper's fixed rule table."""
    t = (text or "").lower()
    one_shot = _token_evidence(t, ONE_SHOT_TOKENS)
    recurring = _token_evidence(t, RECURRING_TOKENS)
    negated_recurring = _negated_recurring_evidence(t)

    evidence = one_shot + recurring
    evidence.extend(f"negated:{item}" for item in negated_recurring)

    if negated_recurring and one_shot:
        return "one-shot", evidence
    if recurring and not negated_recurring:
        return "recurring", evidence
    if recurring and negated_recurring:
        positive_durable = [
            tok
            for tok in recurring
            if tok
            in {
                "until cancelled",
                "until canceled",
                "no expiry",
                "no expiration",
                "without expiry",
                "keep active",
                "keep monitoring",
                "ongoing",
                "continue to remind",
                "keep reminding",
                "auto-renew",
                "monitoring",
                "follow up continuously",
                "持续",
                "一直",
                "长期",
                "直到取消",
                "无期限",
                "持续提醒",
                "持续关注",
                "保持",
            }
        ]
        if positive_durable:
            return "recurring", evidence
    return "one-shot", evidence
