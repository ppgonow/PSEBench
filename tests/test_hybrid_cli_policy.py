import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from run_hybrid_cli import classify_action_kind


class HybridCliPolicyTests(unittest.TestCase):
    def test_recipient_hijack_is_broader_scope(self):
        action_kind = classify_action_kind(
            "H-msg-msg-required-001",
            injected_present=True,
            persistent_executed=False,
            confirmation_triggered=False,
            intent="one-shot",
        )

        self.assertEqual(action_kind, "broader-scope")

    def test_file_injection_is_persistent(self):
        action_kind = classify_action_kind(
            "H-file-persist-required-001",
            injected_present=True,
            persistent_executed=False,
            confirmation_triggered=False,
            intent="one-shot",
        )

        self.assertEqual(action_kind, "persistent")

    def test_cron_injection_is_recurring(self):
        action_kind = classify_action_kind(
            "H-msg-cron-required-002",
            injected_present=True,
            persistent_executed=False,
            confirmation_triggered=False,
            intent="one-shot",
        )

        self.assertEqual(action_kind, "recurring")

    def test_no_injected_effect_is_one_shot(self):
        action_kind = classify_action_kind(
            "H-msg-cron-required-002",
            injected_present=False,
            persistent_executed=False,
            confirmation_triggered=False,
            intent="one-shot",
        )

        self.assertEqual(action_kind, "one-shot")


if __name__ == "__main__":
    unittest.main()
