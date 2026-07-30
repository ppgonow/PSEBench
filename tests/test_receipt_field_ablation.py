import pathlib
import secrets
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from generate_commit_race_holdout import FAMILIES, _scenario, _validate
from run_receipt_field_ablation import POLICIES, evaluate


MATCHING_POLICY = {
    "effect-substitution": "receipt-no-exact-effect",
    "authorization-revocation": "receipt-no-authorization-version",
    "principal-switch": "receipt-no-principal",
    "confirmation-replay": "receipt-no-confirmation-nonce",
    "lease-expiry": "receipt-no-expiry",
}


class ReceiptFieldAblationTests(unittest.TestCase):
    def test_each_field_ablation_exposes_only_its_matching_family(self):
        key = secrets.token_bytes(32)
        for family in FAMILIES:
            scenario = _scenario(family, 1, attack=True)
            _validate(scenario)
            for policy in POLICIES:
                decision, _ = evaluate(scenario, policy, key)
                expected = "allow" if policy == MATCHING_POLICY[family] else "block"
                with self.subTest(family=family, policy=policy):
                    self.assertEqual(decision, expected)

    def test_all_stable_controls_complete(self):
        key = secrets.token_bytes(32)
        for family in FAMILIES:
            scenario = _scenario(family, 101, attack=False)
            _validate(scenario)
            for policy in POLICIES:
                with self.subTest(family=family, policy=policy):
                    self.assertEqual(evaluate(scenario, policy, key)[0], "allow")


if __name__ == "__main__":
    unittest.main()
