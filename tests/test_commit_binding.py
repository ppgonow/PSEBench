import dataclasses
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from commit_binding import (
    CheckContext,
    CommitContext,
    VerificationProfile,
    issue_receipt,
    verify_commit,
    verify_commit_with_profile,
    verify_online_reauthorization,
)
from effect_boundary import EffectSpec
from generate_commit_race_holdout import FAMILIES, _scenario, _validate
from replay_commit_race import evaluate_transition


KEY = b"unit-test-key"


class CommitBindingTests(unittest.TestCase):
    def setUp(self):
        self.effect = EffectSpec("message", target="TEST_CHANNEL")
        self.check = CheckContext("user", 3, 100, 200, "nonce")
        self.receipt = issue_receipt(self.effect, self.effect, self.check, KEY)

    def test_stable_commit_is_allowed(self):
        decision = verify_commit(
            self.receipt,
            self.effect,
            CommitContext("user", 3, 150, "nonce", False),
            KEY,
        )
        self.assertEqual(decision.decision, "allow")

    def test_effect_substitution_is_blocked(self):
        substituted = EffectSpec(
            "message", scope="expanded", target="ATTACKER", provenance="untrusted"
        )
        decision = verify_commit(
            self.receipt,
            substituted,
            CommitContext("user", 3, 150, "nonce", False),
            KEY,
        )
        self.assertEqual(decision.decision, "block")

    def test_context_mutations_are_blocked(self):
        contexts = [
            CommitContext("other", 3, 150, "nonce", False),
            CommitContext("user", 4, 150, "nonce", False),
            CommitContext("user", 3, 99, "nonce", False),
            CommitContext("user", 3, 201, "nonce", False),
            CommitContext("user", 3, 150, "nonce", True),
        ]
        for context in contexts:
            with self.subTest(context=context):
                self.assertEqual(
                    verify_commit(self.receipt, self.effect, context, KEY).decision,
                    "block",
                )

    def test_receipt_tampering_is_blocked(self):
        tampered = dataclasses.replace(self.receipt, authorization_version=4)
        decision = verify_commit(
            tampered,
            self.effect,
            CommitContext("user", 4, 150, "nonce", False),
            KEY,
        )
        self.assertEqual(decision.reason, "receipt authentication failed")

    def test_single_field_profiles_disable_only_named_comparison(self):
        cases = [
            (
                VerificationProfile(principal=False),
                self.effect,
                CommitContext("other", 3, 150, "nonce", False),
            ),
            (
                VerificationProfile(authorization_version=False),
                self.effect,
                CommitContext("user", 4, 150, "nonce", False),
            ),
            (
                VerificationProfile(exact_effect=False),
                EffectSpec("message", scope="expanded", target="other"),
                CommitContext("user", 3, 150, "nonce", False),
            ),
            (
                VerificationProfile(expiry=False),
                self.effect,
                CommitContext("user", 3, 201, "nonce", False),
            ),
            (
                VerificationProfile(confirmation_nonce=False),
                self.effect,
                CommitContext("user", 3, 150, "nonce", True),
            ),
        ]
        for profile, effect, context in cases:
            with self.subTest(profile=profile):
                decision = verify_commit_with_profile(
                    self.receipt, effect, context, KEY, profile
                )
                self.assertEqual(decision.decision, "allow")

    def test_ablation_still_authenticates_complete_receipt(self):
        tampered = dataclasses.replace(self.receipt, authorization_version=4)
        decision = verify_commit_with_profile(
            tampered,
            self.effect,
            CommitContext("user", 4, 150, "nonce", False),
            KEY,
            VerificationProfile(authorization_version=False),
        )
        self.assertEqual(decision.reason, "receipt authentication failed")

    def test_online_reauthorization_uses_current_authority(self):
        stable = verify_online_reauthorization(
            self.effect,
            self.check,
            self.effect,
            CommitContext("user", 3, 150, "nonce", False),
        )
        revoked = verify_online_reauthorization(
            self.effect,
            self.check,
            self.effect,
            CommitContext("user", 4, 150, "nonce", False),
        )
        self.assertEqual(stable.decision, "allow")
        self.assertEqual(revoked.decision, "block")

    def test_all_frozen_transition_families_separate_policies(self):
        for family in FAMILIES:
            scenario = _scenario(family, 1, attack=True)
            _validate(scenario)
            check_once = evaluate_transition(scenario, "check-once")
            commit_bound = evaluate_transition(scenario, "commit-bound")
            with self.subTest(family=family):
                self.assertTrue(check_once["attack_succeeded"])
                self.assertFalse(commit_bound["attack_succeeded"])
                self.assertEqual(commit_bound["policy_decision"], "block")

    def test_benign_controls_preserve_task_completion(self):
        for family in FAMILIES:
            scenario = _scenario(family, 101, attack=False)
            _validate(scenario)
            for policy in ["check-once", "commit-bound"]:
                with self.subTest(family=family, policy=policy):
                    result = evaluate_transition(scenario, policy)
                    self.assertTrue(result["task_completed"])
                    self.assertFalse(result["attack_succeeded"])


if __name__ == "__main__":
    unittest.main()
