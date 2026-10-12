import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
sys.path.insert(0, str(ROOT / "runner"))

from audit_adapter_observer_holdout import audit_cases, corpus_checks
from same_tool_effects import normalize_call
from same_tool_observer import observe_post_state


class AdapterObserverHeldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus_path = ROOT / "scenarios" / "adapter-observer-heldout" / "corpus.json"
        cls.corpus = json.loads(cls.corpus_path.read_text(encoding="utf-8"))

    def test_corpus_is_balanced_and_disjoint(self):
        checks = corpus_checks(self.corpus, self.corpus_path)
        self.assertEqual(checks["case_count"], 48)
        self.assertEqual(checks["unique_case_ids"], 48)
        self.assertEqual(checks["profile_balance"], 1)
        self.assertEqual(checks["workflow_balance"], 1)
        self.assertEqual(checks["case_ids_disjoint_from_normalization"], 1)
        self.assertEqual(checks["legacy_generator_tokens"], 0)

    def test_provider_default_is_observed_as_a_difference(self):
        case = next(
            item
            for item in self.corpus["cases"]
            if item["case_id"] == "AOC-file-provider-default"
        )
        candidate = normalize_call(case["tool_name"], case["candidate"])
        observed = observe_post_state(case["tool_name"], case["post_state"])
        self.assertEqual(observed.decision, "observed")
        self.assertNotEqual(candidate.effect, observed.effect)
        self.assertEqual(candidate.effect.persistence, "one-shot")
        self.assertEqual(observed.effect.persistence, "durable")

    def test_all_heldout_relations_match_the_frozen_expectations(self):
        rows = audit_cases(self.corpus["cases"])
        self.assertEqual(len(rows), 48)
        self.assertTrue(all(row["passed"] for row in rows))


if __name__ == "__main__":
    unittest.main()
