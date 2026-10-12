import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
from audit_external_attack_registry import validate


class ExternalAttackRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads((ROOT / "analysis/external_attack_registry_v1.json").read_text())

    def test_registry_validates(self):
        summary = validate(self.payload)
        self.assertEqual(summary["source_count"], 6)
        self.assertGreaterEqual(summary["family_count"], 5)

    def test_external_source_does_not_own_oracle(self):
        payload = json.loads(json.dumps(self.payload))
        payload["conversion_contract"]["oracle_owner"] = "external_dataset"
        with self.assertRaisesRegex(ValueError, "oracle"):
            validate(payload)

    def test_headline_requires_independent_observer(self):
        payload = json.loads(json.dumps(self.payload))
        payload["conversion_contract"]["independent_observer_required_for_headline"] = False
        with self.assertRaisesRegex(ValueError, "observer"):
            validate(payload)

    def test_duplicate_source_is_rejected(self):
        payload = json.loads(json.dumps(self.payload))
        payload["sources"].append(payload["sources"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate(payload)

    def test_registry_is_offline_only(self):
        payload = json.loads(json.dumps(self.payload))
        payload["freeze_status"] = "live_ready"
        with self.assertRaisesRegex(ValueError, "offline"):
            validate(payload)


if __name__ == "__main__":
    unittest.main()
