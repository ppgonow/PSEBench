import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from effect_boundary import check_effect
from generate_same_tool_native_holdout import conformance_pairs
from same_tool_effects import authorized_effect, normalize_call


class SameToolEffectsTests(unittest.TestCase):
    def test_frozen_conformance_pairs(self):
        pairs = conformance_pairs()
        self.assertEqual(len(pairs), 200)
        for pair in pairs:
            left = normalize_call(pair["tool_name"], pair["left"])
            right = normalize_call(pair["tool_name"], pair["right"])
            with self.subTest(pair_id=pair["pair_id"]):
                if pair["relation"] == "equivalent":
                    self.assertEqual(left.effect, right.effect)
                    self.assertEqual(left.canonical_arguments, right.canonical_arguments)
                else:
                    self.assertNotEqual(left.effect, right.effect)

    def test_authorization_ignores_digest_but_rejects_boundary_change(self):
        safe = {
            "name": "Reminder test",
            "fire_at": "2030-01-01T00:10:00Z",
            "recurrence": None,
        }
        grant = authorized_effect("reminder", safe)
        proposed = normalize_call("schedule_reminder", safe).effect
        recurring = normalize_call(
            "schedule_reminder", {**safe, "recurrence": "daily"}
        ).effect
        self.assertEqual(check_effect(grant, proposed).decision, "allow")
        self.assertEqual(check_effect(grant, recurring).decision, "block")

    def test_path_traversal_and_naive_timestamp_fail_closed(self):
        with self.assertRaises(ValueError):
            normalize_call(
                "write_file",
                {"path": "/workspace/session/../startup/a", "content": "x"},
            )
        with self.assertRaises(ValueError):
            normalize_call(
                "schedule_reminder",
                {"name": "x", "fire_at": "2030-01-01T00:10:00", "recurrence": None},
            )


if __name__ == "__main__":
    unittest.main()
