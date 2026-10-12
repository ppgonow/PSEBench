import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
sys.path.insert(0, str(ROOT / "runner"))

from audit_posix_file_provider import audit, integrity
from posix_file_service import CommitResult, PosixFileSandbox


class PosixFileProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus_path = ROOT / "scenarios" / "posix-file-provider-heldout" / "corpus.json"
        cls.corpus = json.loads(cls.corpus_path.read_text(encoding="utf-8"))

    def test_frozen_corpus_is_balanced(self):
        self.assertEqual(len(self.corpus["cases"]), 24)
        self.assertEqual(
            {case["profile"] for case in self.corpus["cases"]},
            {
                "clean-create",
                "target-symlink",
                "parent-symlink",
                "target-hardlink",
                "parent-swap",
                "aggregate-budget",
            },
        )

    def test_secure_commit_rejects_target_symlink(self):
        case = next(case for case in self.corpus["cases"] if case["profile"] == "target-symlink")
        rows = audit([case])
        self.assertEqual(rows[0]["secure_decision"], "block")
        self.assertEqual(rows[0]["secure_committed"], 0)
        self.assertEqual(rows[0]["naive_label"], "unsafe")

    def test_secure_commit_rejects_hardlink_and_parent_swap(self):
        cases = [
            case
            for case in self.corpus["cases"]
            if case["profile"] in {"target-hardlink", "parent-swap"}
        ][:2]
        rows = audit(cases)
        self.assertTrue(all(row["secure_decision"] == "block" for row in rows))
        self.assertTrue(all(row["naive_label"] == "unsafe" for row in rows))

    def test_full_audit_has_no_secure_unsafe_commit(self):
        with tempfile.TemporaryDirectory(prefix="psebench-posix-test-"):
            rows = audit(self.corpus["cases"])
        self.assertEqual(len(rows), 24)
        self.assertTrue(all(row["secure_passed"] for row in rows))
        self.assertTrue(all(row["naive_passed"] for row in rows))
        self.assertEqual(
            sum(
                int(row["secure_committed"])
                * int(row["secure_first_effect_label"] == "unsafe")
                + int(row["secure_second_committed"])
                * int(row["secure_second_effect_label"] == "unsafe")
                for row in rows
            ),
            0,
        )
        checks = integrity(self.corpus, self.corpus_path, rows)
        self.assertEqual(checks["candidate_effect_count"], 28)
        self.assertEqual(checks["authorized_effect_count"], 8)
        self.assertEqual(checks["unsafe_effect_count"], 20)
        self.assertEqual(checks["naive_unsafe_committed_effects"], 20)
        self.assertEqual(checks["secure_authorized_effects_committed"], 8)
        self.assertEqual(checks["secure_unsafe_effects_blocked"], 20)
        self.assertEqual(checks["naive_authorized_effects_committed"], 8)
        self.assertEqual(checks["naive_namespace_or_link_effects"], 16)
        self.assertEqual(checks["naive_budget_overflow_effects"], 4)

    def test_observer_is_not_returned_by_commit_path(self):
        self.assertNotIn("observation", CommitResult.__dataclass_fields__)


if __name__ == "__main__":
    unittest.main()
