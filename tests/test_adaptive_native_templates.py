import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))

from analyze_adaptive_native_templates import exact_mcnemar, summary_rows, wilson_interval


class AdaptiveNativeTemplateTests(unittest.TestCase):
    def test_template_level_pairing(self):
        details = []
        for index in range(5):
            details.append(
                {
                    "requested_alias": "alias-a",
                    "boundary": "cron",
                    "template_index": index,
                    "instances": 4,
                    "valid_instances": 4,
                    "permissive_attack_instances": 1 if index < 3 else 0,
                    "permissive_attack_any": int(index < 3),
                    "permissive_task_instances": 4,
                    "permissive_task_all": 1,
                    "IACG_attack_instances": 0,
                    "IACG_attack_any": 0,
                    "IACG_task_instances": 4,
                    "IACG_task_all": 1,
                }
            )
        summary = next(row for row in summary_rows(details) if row["boundary"] == "overall")
        self.assertEqual(summary["semantic_templates"], 5)
        self.assertEqual(summary["permissive_attack_templates"], 3)
        self.assertEqual(summary["permissive_only_templates"], 3)
        self.assertEqual(summary["template_exact_mcnemar_p"], 0.25)

    def test_statistics(self):
        self.assertEqual(exact_mcnemar(10, 0), 0.001953125)
        low, high = wilson_interval(0, 20)
        self.assertEqual(low, 0.0)
        self.assertAlmostEqual(high, 0.16113, places=5)


if __name__ == "__main__":
    unittest.main()
