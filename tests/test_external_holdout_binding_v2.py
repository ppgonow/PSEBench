import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
from audit_external_holdout_binding_v2 import validate


class ExternalHoldoutBindingV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads((ROOT / "analysis/external_holdout_binding_manifest_v2.json").read_text())

    def test_record_bindings_are_complete_but_conversion_pending(self):
        summary = validate(self.payload)
        self.assertEqual(summary["record_bindings"], 72)
        self.assertEqual(summary["attack_bindings"], 36)
        self.assertEqual(summary["benign_bindings"], 36)
        self.assertEqual(summary["scheduled_units"], 0)
        self.assertEqual(set(summary["attack_families"].values()), {6})

    def test_duplicate_hash_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        payload["item_bindings"][1]["source_item_hash"] = payload["item_bindings"][0]["source_item_hash"]
        with self.assertRaisesRegex(ValueError, "unique SHA"):
            validate(payload)

    def test_completed_transformation_is_rejected_before_conversion(self):
        payload = copy.deepcopy(self.payload)
        payload["item_bindings"][0]["transformation_status"] = "complete"
        with self.assertRaisesRegex(ValueError, "prematurely"):
            validate(payload)

    def test_live_units_remain_zero(self):
        payload = copy.deepcopy(self.payload)
        payload["scheduled_units"] = 1
        with self.assertRaisesRegex(ValueError, "schedule"):
            validate(payload)


if __name__ == "__main__":
    unittest.main()
