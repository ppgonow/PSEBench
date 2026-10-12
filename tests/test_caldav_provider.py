import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "tmp" / "radicale_runtime"
sys.path.insert(0, str(ROOT / "analysis"))
sys.path.insert(0, str(ROOT / "runner"))

from audit_caldav_provider import run_case  # noqa: E402
from radicale_caldav_service import (  # noqa: E402
    AUTHORIZED_COLLECTION,
    RadicaleCalDAVServer,
    event_body,
    parse_event,
)


class CalDAVProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus_path = ROOT / "scenarios" / "caldav-provider-heldout" / "corpus.json"
        cls.corpus = json.loads(cls.corpus_path.read_text(encoding="utf-8"))

    def test_frozen_corpus_is_balanced(self):
        self.assertEqual(len(self.corpus["cases"]), 28)
        self.assertEqual(
            {case["profile"] for case in self.corpus["cases"]},
            {
                "clean-one-shot",
                "provider-normalization",
                "recurrence-injection",
                "endpoint-swap",
                "stale-etag",
                "aggregate-overflow",
                "partial-update-injection",
            },
        )

    def test_ical_parser_unfolds_and_preserves_recurrence(self):
        body = event_body(
            "u1",
            "Morning review",
            recurrence="FREQ=DAILY;COUNT=3",
            variant="folded-summary",
        )
        self.assertEqual(parse_event(body), ("u1", "Morning review", "FREQ=DAILY;COUNT=3"))

    @unittest.skipUnless(RUNTIME.is_dir(), "optional Radicale runtime is not installed")
    def test_real_provider_reports_recurring_post_state(self):
        case = next(
            case
            for case in self.corpus["cases"]
            if case["profile"] == "recurrence-injection"
        )
        row = run_case(case, "naive", RUNTIME)
        self.assertEqual(row["http_statuses"], "201")
        self.assertEqual(row["observer_label"], "unsafe")
        self.assertEqual(row["authorized_event_count"], 3)

    @unittest.skipUnless(RUNTIME.is_dir(), "optional Radicale runtime is not installed")
    def test_secure_provider_path_rejects_stale_etag(self):
        case = next(
            case
            for case in self.corpus["cases"]
            if case["profile"] == "stale-etag"
        )
        row = run_case(case, "secure", RUNTIME)
        self.assertEqual(row["http_statuses"], "412")
        self.assertEqual(row["observer_label"], "etag-block")
        self.assertEqual(row["unsafe_committed_effects"], 0)


if __name__ == "__main__":
    unittest.main()

