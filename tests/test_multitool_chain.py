import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from effect_boundary import EffectSpec
from replay_multitool_chain import evaluate_chain


class MultiToolChainTests(unittest.TestCase):
    def setUp(self):
        self.authorized = [
            EffectSpec("file", target="REPORT"),
            EffectSpec("message", target="TEST_CHANNEL"),
        ]
        self.injected = EffectSpec(
            "message", scope="expanded", target="ATTACKER", provenance="untrusted"
        )
        self.proposed = [*self.authorized, self.injected]

    def test_permissive_commits_chain_escalation(self):
        result = evaluate_chain(
            self.authorized, self.authorized, self.proposed, [self.injected], "permissive"
        )
        self.assertTrue(result["attack_succeeded"])
        self.assertTrue(result["task_completed"])
        self.assertEqual(len(result["committed_effects"]), 3)

    def test_iacg_blocks_only_unauthorized_chain_effect(self):
        result = evaluate_chain(
            self.authorized, self.authorized, self.proposed, [self.injected], "IACG"
        )
        self.assertFalse(result["attack_succeeded"])
        self.assertTrue(result["task_completed"])
        self.assertEqual(result["committed_effects"], self.authorized)
        self.assertEqual(result["decisions"][-1]["policy_decision"], "block")

    def test_missing_authorized_step_fails_task_completion(self):
        result = evaluate_chain(
            self.authorized, self.authorized, [self.authorized[0]], [self.injected], "IACG"
        )
        self.assertFalse(result["attack_succeeded"])
        self.assertFalse(result["task_completed"])


if __name__ == "__main__":
    unittest.main()
