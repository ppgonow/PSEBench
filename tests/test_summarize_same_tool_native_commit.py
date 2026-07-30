import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))

from summarize_same_tool_native_commit import (  # noqa: E402
    cluster_bootstrap,
    exact_cluster_signflip,
    exposure_paired,
    holm_adjust_attack,
)


class SameToolExposurePairTests(unittest.TestCase):
    def row(self, template_id, exposure, unsafe, permissive_attack):
        return {
            "requested_alias": "gpt-5.5",
            "template_id": template_id,
            "workflow": "message",
            "carrier": "message",
            "exposure": exposure,
            "unsafe_first_proposal": unsafe,
            "permissive_attack": permissive_attack,
            "IACG_attack": 0,
            "permissive_task": 1,
            "IACG_task": 1,
        }

    def test_clean_injected_mcnemar_is_same_template_paired(self):
        detail = [
            self.row("template-1", "clean", 0, 0),
            self.row("template-1", "injected", 1, 1),
            self.row("template-2", "clean", 0, 0),
            self.row("template-2", "injected", 0, 0),
        ]
        rows = exposure_paired(detail)
        unsafe = next(
            row
            for row in rows
            if row["scope"] == "overall"
            and row["outcome"] == "unsafe_first_proposal"
        )
        self.assertEqual(unsafe["n_pairs"], 2)
        self.assertEqual(unsafe["clean_yes"], 0)
        self.assertEqual(unsafe["injected_yes"], 1)
        self.assertEqual(unsafe["clean_only"], 0)
        self.assertEqual(unsafe["injected_only"], 1)
        self.assertEqual(unsafe["exact_mcnemar_p"], 1.0)

    def test_missing_exposure_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unpaired clean/injected"):
            exposure_paired([self.row("template-1", "clean", 0, 0)])

    def test_cluster_signflip_uses_block_level_differences(self):
        self.assertEqual(exact_cluster_signflip([4, 4, 0]), 0.5)
        self.assertEqual(exact_cluster_signflip([0, 0]), 1.0)

    def test_holm_adjustment_is_monotone(self):
        rows = [
            {"requested_alias": model, "outcome": "attack", "exact_mcnemar_p": p}
            for model, p in zip(
                ("gpt-5.5", "grok-4.5", "gpt-5.4", "gpt-5.6-sol"),
                (0.0625, 5.960464477539063e-08, 0.125, 0.0625),
            )
        ]
        adjusted = {row["requested_alias"]: row for row in holm_adjust_attack(rows)}
        self.assertLess(adjusted["grok-4.5"]["holm_adjusted_p"], 0.05)
        self.assertEqual(adjusted["gpt-5.5"]["holm_adjusted_p"], 0.1875)
        self.assertEqual(adjusted["gpt-5.4"]["holm_adjusted_p"], 0.1875)

    def test_cluster_bootstrap_resamples_twelve_whole_blocks(self):
        rows = []
        for model in ("gpt-5.5", "grok-4.5", "gpt-5.4", "gpt-5.6-sol"):
            for carrier in ("message", "retrieved-document", "tool-output"):
                for style in range(1, 5):
                    for workflow in ("reminder", "file", "calendar", "message"):
                        rows.append(
                            {
                                "requested_alias": model,
                                "exposure": "injected",
                                "template_id": f"{workflow}-{style}",
                                "carrier": carrier,
                                "permissive_attack": 1,
                                "IACG_attack": 0,
                            }
                        )
        output = cluster_bootstrap(rows)
        self.assertEqual(len(output), 4)
        self.assertTrue(all(row["n_style_blocks"] == 12 for row in output))
        self.assertTrue(all(row["estimate"] == 1.0 for row in output))


if __name__ == "__main__":
    unittest.main()
