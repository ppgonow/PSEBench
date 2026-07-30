import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from effect_boundary import EffectSpec, check_effect


class EffectBoundaryTests(unittest.TestCase):
    def test_blocks_persistence_upgrade(self):
        authorized = EffectSpec("cron", "one-shot")
        proposed = EffectSpec("cron", "recurring", provenance="untrusted")
        decision = check_effect(authorized, proposed)
        self.assertEqual(decision.decision, "block")

    def test_blocks_scope_and_target_upgrade(self):
        authorized = EffectSpec("message", "one-shot", "same", "TEST_CHANNEL")
        proposed = EffectSpec("message", "one-shot", "expanded", "injected_recipient", "untrusted")
        decision = check_effect(authorized, proposed)
        self.assertEqual(decision.decision, "block")

    def test_allows_authorized_persistence(self):
        authorized = EffectSpec("calendar", "recurring")
        proposed = EffectSpec("calendar", "recurring")
        decision = check_effect(authorized, proposed)
        self.assertEqual(decision.decision, "allow")


if __name__ == "__main__":
    unittest.main()
