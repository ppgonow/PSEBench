import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
from audit_external_holdout_binding import validate


class ExternalHoldoutBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads((ROOT / "analysis/external_holdout_binding_manifest_v1.json").read_text())

    def test_manifest_has_no_fabricated_item_bindings(self):
        summary = validate(self.payload)
        self.assertEqual(summary["candidate_sources"], 6)
        self.assertEqual(summary["item_bindings"], 0)
        self.assertEqual(summary["scheduled_units"], 0)

    def test_partial_item_binding_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        payload["item_bindings"] = [{"source_item_hash": "0" * 64}]
        with self.assertRaisesRegex(ValueError, "partial item bindings"):
            validate(payload)

    def test_live_authorization_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        payload["live_execution_authorized"] = True
        with self.assertRaisesRegex(ValueError, "authorizes live"):
            validate(payload)

    def test_duplicate_candidates_are_rejected(self):
        payload = copy.deepcopy(self.payload)
        payload["candidate_sources"].append(payload["candidate_sources"][0])
        with self.assertRaisesRegex(ValueError, "six"):
            validate(payload)


if __name__ == "__main__":
    unittest.main()
