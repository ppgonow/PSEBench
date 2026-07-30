import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))

from independent_unit_analysis import (
    Outcome,
    exact_mcnemar,
    load_condition,
    load_paired_outcomes,
    summarize_pair,
)


class IndependentUnitAnalysisTests(unittest.TestCase):
    def test_exact_mcnemar(self):
        self.assertEqual(exact_mcnemar(0, 0), 1.0)
        self.assertAlmostEqual(exact_mcnemar(10, 0), 0.001953125)
        self.assertAlmostEqual(exact_mcnemar(6, 0), 0.03125)

    def test_summary_requires_identical_ids(self):
        baseline = {"a": Outcome("a", True, True)}
        iacg = {"b": Outcome("b", False, True)}
        with self.assertRaisesRegex(ValueError, "scenario mismatch"):
            summarize_pair("test", "surface", baseline, iacg)

    def test_load_condition_rejects_duplicate_scenarios(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for run_name in ("one", "two"):
                target = root / run_name / "same"
                target.mkdir(parents=True)
                (target / "final.json").write_text(
                    json.dumps(
                        {
                            "manual_labels": {
                                "attack_succeeded": "no",
                                "task_completed": "yes",
                            }
                        }
                    ),
                    encoding="utf-8",
                )
            with self.assertRaisesRegex(ValueError, "duplicate scenario"):
                load_condition(root, ("one", "two"))

    def test_summary_counts_paired_outcomes(self):
        baseline = {
            "a": Outcome("a", True, True),
            "b": Outcome("b", False, True),
        }
        iacg = {
            "a": Outcome("a", False, True),
            "b": Outcome("b", False, False),
        }
        row = summarize_pair("test", "surface", baseline, iacg)
        self.assertEqual(row["n_unique_scenarios"], 2)
        self.assertEqual(row["baseline_attack_yes"], 1)
        self.assertEqual(row["iacg_attack_yes"], 0)
        self.assertEqual(row["baseline_yes_iacg_no"], 1)
        self.assertEqual(row["baseline_no_iacg_yes"], 0)
        self.assertEqual(row["iacg_task_yes"], 1)

    def test_frozen_outcomes_are_used_when_all_raw_runs_are_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frozen = root / "outcomes.csv"
            lines = [
                "slice,execution_surface,condition,scenario_id,attack_succeeded,task_completed"
            ]
            from independent_unit_analysis import PAIR_SPECS

            for index, spec in enumerate(PAIR_SPECS):
                scenario_id = f"scenario-{index}"
                lines.append(
                    f"{spec.name},{spec.execution_surface},baseline,{scenario_id},yes,yes"
                )
                lines.append(
                    f"{spec.name},{spec.execution_surface},iacg,{scenario_id},no,yes"
                )
            frozen.write_text("\n".join(lines) + "\n", encoding="utf-8")
            pairs, source = load_paired_outcomes(root / "runs", frozen)
            self.assertEqual(source, "frozen_outcome_table")
            self.assertEqual(len(pairs), 6)

    def test_partial_raw_inventory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "g1fixed-permissive").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "partial independent raw-run inventory"):
                load_paired_outcomes(root, Path(directory) / "outcomes.csv")


if __name__ == "__main__":
    unittest.main()
