import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from intent_policy import infer_intent


class IntentPolicyTests(unittest.TestCase):
    def test_negated_recurring_cues_remain_one_shot(self):
        text = "Create a one-time reminder. Do not make it recurring; no daily or weekly repeats."

        intent, evidence = infer_intent(text)

        self.assertEqual(intent, "one-shot")
        self.assertTrue(any(str(item).startswith("negated:") for item in evidence))

    def test_implicit_durability_is_recurring(self):
        text = "Keep reminding me about this until cancelled with no expiry."

        intent, evidence = infer_intent(text)

        self.assertEqual(intent, "recurring")
        self.assertIn("until cancelled", evidence)
        self.assertIn("no expiry", evidence)

    def test_ambiguous_request_defaults_to_one_shot(self):
        intent, evidence = infer_intent("Remind me about the project update.")

        self.assertEqual(intent, "one-shot")
        self.assertEqual(evidence, [])


if __name__ == "__main__":
    unittest.main()
