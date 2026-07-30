"""Commit-time binding for authorization decisions in local state-machine replay."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
from typing import Optional

from effect_boundary import EffectSpec, check_effect


@dataclass(frozen=True)
class CheckContext:
    principal: str
    authorization_version: int
    checked_at: int
    expires_at: int
    confirmation_nonce: Optional[str] = None


@dataclass(frozen=True)
class CommitContext:
    principal: str
    authorization_version: int
    committed_at: int
    confirmation_nonce: Optional[str] = None
    nonce_consumed: bool = False


@dataclass(frozen=True)
class CommitReceipt:
    principal: str
    authorization_version: int
    checked_effect: EffectSpec
    checked_at: int
    expires_at: int
    confirmation_nonce: Optional[str]
    authentication_tag: str

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["checked_effect"] = self.checked_effect.to_dict()
        return payload


@dataclass(frozen=True)
class CommitDecision:
    decision: str
    reason: str


@dataclass(frozen=True)
class VerificationProfile:
    """Named commit-state comparisons enabled by a receipt verifier."""

    principal: bool = True
    authorization_version: bool = True
    exact_effect: bool = True
    expiry: bool = True
    confirmation_nonce: bool = True


FULL_VERIFICATION = VerificationProfile()


def _receipt_payload(
    principal: str,
    authorization_version: int,
    checked_effect: EffectSpec,
    checked_at: int,
    expires_at: int,
    confirmation_nonce: Optional[str],
) -> bytes:
    payload = {
        "authorization_version": authorization_version,
        "checked_at": checked_at,
        "checked_effect": checked_effect.to_dict(),
        "confirmation_nonce": confirmation_nonce,
        "expires_at": expires_at,
        "principal": principal,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def issue_receipt(
    authorized: EffectSpec,
    proposed: EffectSpec,
    context: CheckContext,
    authentication_key: bytes,
) -> CommitReceipt:
    boundary = check_effect(authorized, proposed)
    if boundary.decision != "allow":
        raise ValueError(f"cannot issue receipt: {boundary.reason}")
    if context.expires_at < context.checked_at:
        raise ValueError("receipt expiry precedes check time")
    payload = _receipt_payload(
        context.principal,
        context.authorization_version,
        proposed,
        context.checked_at,
        context.expires_at,
        context.confirmation_nonce,
    )
    tag = hmac.new(authentication_key, payload, hashlib.sha256).hexdigest()
    return CommitReceipt(
        principal=context.principal,
        authorization_version=context.authorization_version,
        checked_effect=proposed,
        checked_at=context.checked_at,
        expires_at=context.expires_at,
        confirmation_nonce=context.confirmation_nonce,
        authentication_tag=tag,
    )


def verify_commit(
    receipt: CommitReceipt,
    commit_effect: EffectSpec,
    context: CommitContext,
    authentication_key: bytes,
) -> CommitDecision:
    return verify_commit_with_profile(
        receipt,
        commit_effect,
        context,
        authentication_key,
        FULL_VERIFICATION,
    )


def verify_commit_with_profile(
    receipt: CommitReceipt,
    commit_effect: EffectSpec,
    context: CommitContext,
    authentication_key: bytes,
    profile: VerificationProfile,
) -> CommitDecision:
    payload = _receipt_payload(
        receipt.principal,
        receipt.authorization_version,
        receipt.checked_effect,
        receipt.checked_at,
        receipt.expires_at,
        receipt.confirmation_nonce,
    )
    expected_tag = hmac.new(authentication_key, payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(receipt.authentication_tag, expected_tag):
        return CommitDecision("block", "receipt authentication failed")
    if profile.principal and context.principal != receipt.principal:
        return CommitDecision("block", "principal changed after authorization")
    if (
        profile.authorization_version
        and context.authorization_version != receipt.authorization_version
    ):
        return CommitDecision("block", "authorization version changed before commit")
    if profile.exact_effect and commit_effect != receipt.checked_effect:
        return CommitDecision("block", "committed effect differs from checked effect")
    if context.committed_at < receipt.checked_at:
        return CommitDecision("block", "commit time precedes authorization check")
    if profile.expiry and context.committed_at > receipt.expires_at:
        return CommitDecision("block", "authorization receipt expired before commit")
    if profile.confirmation_nonce:
        if context.confirmation_nonce != receipt.confirmation_nonce:
            return CommitDecision("block", "confirmation nonce differs from receipt")
        if receipt.confirmation_nonce is not None and context.nonce_consumed:
            return CommitDecision("block", "confirmation nonce was already consumed")
    return CommitDecision("allow", "commit context matches authenticated receipt")


def verify_online_reauthorization(
    authorized_effect: EffectSpec,
    authorized_context: CheckContext,
    commit_effect: EffectSpec,
    current_context: CommitContext,
) -> CommitDecision:
    """Re-evaluate a trusted grant against authoritative state at commit.

    This deliberately strong baseline assumes the effect service receives the
    original trusted grant and can read current authority in the same commit
    boundary. It uses no cached allow and no receipt.
    """

    if current_context.principal != authorized_context.principal:
        return CommitDecision("block", "current principal differs from trusted grant")
    if current_context.authorization_version != authorized_context.authorization_version:
        return CommitDecision("block", "trusted grant is not the current authorization")
    boundary = check_effect(authorized_effect, commit_effect)
    if boundary.decision != "allow":
        return CommitDecision("block", f"current grant rejects effect: {boundary.reason}")
    if current_context.committed_at < authorized_context.checked_at:
        return CommitDecision("block", "commit time precedes trusted grant")
    if current_context.committed_at > authorized_context.expires_at:
        return CommitDecision("block", "trusted grant expired before commit")
    if current_context.confirmation_nonce != authorized_context.confirmation_nonce:
        return CommitDecision("block", "current confirmation differs from trusted grant")
    if (
        authorized_context.confirmation_nonce is not None
        and current_context.nonce_consumed
    ):
        return CommitDecision("block", "current confirmation was already consumed")
    return CommitDecision("allow", "current authority permits effect at commit")
