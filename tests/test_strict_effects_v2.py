import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
sys.path.insert(0, str(ROOT / "analysis"))

from audit_adaptive_effect_v2 import audit_rows  # noqa: E402
from strict_effects_v2 import (  # noqa: E402
    SchemaReviewRequired,
    check_exact_candidate_v2,
    check_sequence_v2,
    normalize_call_v2,
)


class StrictEffectsV2Tests(unittest.TestCase):
    def setUp(self):
        self.safe = {
            "name": "Reminder test",
            "fire_at": "2030-01-01T00:10:00Z",
            "recurrence": None,
        }

    def test_unknown_fields_require_review(self):
        with self.assertRaises(SchemaReviewRequired):
            normalize_call_v2(
                "schedule_reminder", {**self.safe, "provider_default": True}
            )

    def test_exact_declared_field_substitution_is_blocked(self):
        authorized = normalize_call_v2("schedule_reminder", self.safe)
        changed = normalize_call_v2(
            "schedule_reminder",
            {**self.safe, "fire_at": "2031-01-01T00:10:00Z"},
        )
        self.assertEqual(
            check_exact_candidate_v2(authorized, changed).decision, "block"
        )

    def test_sequence_cardinality_is_checked_before_normalization(self):
        authorized = normalize_call_v2("schedule_reminder", self.safe)
        calls = [
            ("schedule_reminder", dict(self.safe)),
            ("schedule_reminder", dict(self.safe)),
        ]
        decision = check_sequence_v2(authorized, calls, max_commits=1)
        self.assertEqual(decision.decision, "block")
        self.assertEqual(decision.normalized_count, 0)

    def test_deterministic_adaptive_matrix_closes_enumerated_unsafe_cases(self):
        rows = audit_rows()
        self.assertEqual(len(rows), 42)
        self.assertGreater(
            sum(
                row["security_label"] == "unsafe"
                and row["legacy_v1_decision"] == "allow"
                for row in rows
            ),
            0,
        )
        self.assertEqual(
            sum(
                row["security_label"] == "unsafe"
                and row["strict_v2_decision"] == "allow"
                for row in rows
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()

