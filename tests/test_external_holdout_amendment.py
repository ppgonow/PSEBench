import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
from audit_external_holdout_amendment import validate


class ExternalHoldoutAmendmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads((ROOT / "analysis/external_holdout_amendment_v1.json").read_text())

    def test_design_has_zero_live_units(self):
        summary = validate(self.payload)
        self.assertEqual(summary["attack_templates"], 36)
        self.assertEqual(summary["scenario_ids"], 72)
        self.assertEqual(summary["per_model_provider_trajectories"], 360)
        self.assertEqual(summary["scheduled_units"], 0)

    def test_bindings_are_not_allowed_in_design_freeze(self):
        payload = copy.deepcopy(self.payload)
        payload["source_disjointness"]["source_bindings"] = [{"source_item_hash": "x"}]
        with self.assertRaisesRegex(ValueError, "execution bindings"):
            validate(payload)

    def test_count_mismatch_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        payload["planned_units"]["per_model_provider"] = 1
        with self.assertRaisesRegex(ValueError, "denominator"):
            validate(payload)

    def test_observer_requirement_cannot_be_removed(self):
        payload = copy.deepcopy(self.payload)
        payload["outcomes"]["observer"] = "local ledger"
        with self.assertRaisesRegex(ValueError, "observer"):
            validate(payload)


if __name__ == "__main__":
    unittest.main()
