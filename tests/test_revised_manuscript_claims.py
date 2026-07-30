import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))

from audit_revised_manuscript_claims import run_audit  # noqa: E402


class RevisedManuscriptClaimAuditTests(unittest.TestCase):
    def test_current_manuscript_claims_match_artifacts(self):
        source = (
            ROOT
            / "paper_versions"
            / "infocom_nature_polished_2026-07-22"
            / "src"
        )
        if not source.is_dir():
            self.skipTest(
                "review manuscript is intentionally excluded from the anonymous artifact"
            )
        rows = run_audit(source)
        self.assertGreaterEqual(len(rows), 20)
        self.assertEqual(
            [row["check_id"] for row in rows if row["status"] == "fail"], []
        )


if __name__ == "__main__":
    unittest.main()
