import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
sys.path.insert(0, str(ROOT / "analysis"))

from run_confirmation_decision import (
    RequestBudget,
    RequestBudgetExceeded,
    RetryableAPIError,
    _load,
    load_request_attempts,
    load_seen,
    parse_decision,
    redact_error,
    request_with_retries,
    select_scenarios,
)
from summarize_confirmation_decision import (
    exact_mcnemar,
    holm_adjust,
    load_deduplicated_rows,
    paired_framing_summary,
    validate_matrix,
)
from confirmation_power_analysis import exact_power, minimum_consistent_discordance


class ConfirmationDecisionTests(unittest.TestCase):
    def test_matrix_is_balanced(self):
        scenarios = [_load(path) for path in select_scenarios()]
        self.assertEqual(len(scenarios), 20)
        self.assertEqual(sum(sc.get("type") == "benign" for sc in scenarios), 10)
        self.assertEqual(sum(sc.get("type") == "attack" for sc in scenarios), 10)

    def test_parses_confirmation_json(self):
        decision, error = parse_decision(
            '{"approve": false, "safe_fallback": true, "reason": "not authorized", "evidence": ""}'
        )
        self.assertEqual(error, "")
        self.assertFalse(decision["approve"])
        self.assertTrue(decision["safe_fallback"])

    def test_retry_backoff_is_bounded(self):
        attempts = []
        delays = []

        def operation():
            attempts.append(1)
            if len(attempts) == 1:
                raise RetryableAPIError(429, retry_after=3.0)
            if len(attempts) == 2:
                raise RetryableAPIError(503)
            return "ok"

        budget = RequestBudget(5)
        value, used_attempts = request_with_retries(
            operation,
            budget,
            max_retries=2,
            retry_backoff=2.0,
            max_retry_delay=4.0,
            sleep_fn=delays.append,
        )
        self.assertEqual(value, "ok")
        self.assertEqual(used_attempts, 3)
        self.assertEqual(budget.used, 3)
        self.assertEqual(delays, [3.0, 4.0])

    def test_request_budget_stops_retries(self):
        budget = RequestBudget(1)
        with self.assertRaises(RequestBudgetExceeded):
            request_with_retries(
                lambda: (_ for _ in ()).throw(RetryableAPIError(503)),
                budget,
                max_retries=2,
                retry_backoff=0.0,
                max_retry_delay=0.0,
                sleep_fn=lambda _: None,
            )
        self.assertEqual(budget.used, 1)

    def test_terminal_retry_failure_records_all_consumed_attempts(self):
        budget = RequestBudget(5)
        before = budget.used
        with self.assertRaises(RetryableAPIError):
            request_with_retries(
                lambda: (_ for _ in ()).throw(RetryableAPIError(503)),
                budget,
                max_retries=2,
                retry_backoff=0.0,
                max_retry_delay=0.0,
                sleep_fn=lambda _: None,
            )
        self.assertEqual(budget.used - before, 3)

    def test_error_redaction_removes_key_and_bearer(self):
        key = "unit-test-secret-value"
        fake_prefixed_key = "s" + "k-" + "A" * 30
        redacted = redact_error(
            RuntimeError(f"request failed Bearer {key} key={key} alternate={fake_prefixed_key}"),
            key,
        )
        self.assertNotIn(key, redacted)
        self.assertNotIn(fake_prefixed_key, redacted)
        self.assertIn("<redacted-key>", redacted)

    def test_resume_seen_set_ignores_failed_rows(self):
        rows = [
            {"model": "m", "framing": "neutral", "scenario_id": "s", "api_error": "timeout"},
            {"model": "m", "framing": "contaminated", "scenario_id": "s", "api_error": ""},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rows.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            seen = load_seen(path)
        self.assertNotIn(("m", "neutral", "s"), seen)
        self.assertIn(("m", "contaminated", "s"), seen)

    def test_resume_request_budget_counts_prior_attempts(self):
        rows = [
            {"http_attempts": 3},
            {"http_attempts": 0},
            {"legacy_row": True},
            {"http_attempts": 2},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rows.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            attempts = load_request_attempts(path)
        self.assertEqual(attempts, 7)

    def test_cli_resume_cannot_reset_request_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = pathlib.Path(directory)
            path = output_dir / "budget-check_raw.jsonl"
            rows = [
                {
                    "model": "m",
                    "framing": "neutral",
                    "scenario_id": "failed",
                    "api_error": "timeout",
                    "http_attempts": 1,
                }
                for _ in range(150)
            ]
            path.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
            )
            environment = os.environ.copy()
            environment.pop("OPENAI_API_KEY", None)
            environment.pop("OPENAI_BASE_URL", None)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "runner" / "run_confirmation_decision.py"),
                    "--models",
                    "m",
                    "--run-id",
                    "budget-check",
                    "--output-dir",
                    str(output_dir),
                    "--resume",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )
        combined = completed.stdout + completed.stderr
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("HTTP request budget exhausted (150/150)", combined)
        self.assertNotIn("missing OPENAI_API_KEY", combined)

    def test_summary_deduplicates_resume_rows(self):
        rows = [
            {"model": "m", "framing": "neutral", "scenario_id": "s1", "api_error": "timeout"},
            {"model": "m", "framing": "neutral", "scenario_id": "s1", "api_error": "", "approve": True},
            {"model": "m", "framing": "neutral", "scenario_id": "s2", "api_error": "", "approve": False},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rows.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            raw, deduplicated = load_deduplicated_rows(path)
        self.assertEqual(len(raw), 3)
        self.assertEqual(len(deduplicated), 2)
        final_s1 = next(row for row in deduplicated if row["scenario_id"] == "s1")
        self.assertTrue(final_s1["approve"])

    def test_summary_requires_complete_expected_matrix(self):
        scenario_ids = ["s1", "s2"]
        complete = {
            (model, framing): [{"scenario_id": scenario_id} for scenario_id in scenario_ids]
            for model in ["m1", "m2", "m3"]
            for framing in ["neutral", "contaminated"]
        }
        validate_matrix(
            complete,
            expected_models=["m1", "m2", "m3"],
            expected_framings=["neutral", "contaminated"],
            expected_per_cell=2,
        )
        missing = dict(complete)
        del missing[("m3", "contaminated")]
        with self.assertRaisesRegex(ValueError, "missing=m3/contaminated"):
            validate_matrix(
                missing,
                expected_models=["m1", "m2", "m3"],
                expected_framings=["neutral", "contaminated"],
                expected_per_cell=2,
            )

    def test_summary_rejects_mismatched_scenario_ids(self):
        groups = {
            ("m", "neutral"): [{"scenario_id": "s1"}, {"scenario_id": "s2"}],
            ("m", "contaminated"): [{"scenario_id": "s1"}, {"scenario_id": "s3"}],
        }
        with self.assertRaisesRegex(ValueError, "scenario IDs differ"):
            validate_matrix(
                groups,
                expected_models=["m"],
                expected_framings=["neutral", "contaminated"],
                expected_per_cell=2,
            )

    def test_summary_rejects_unresolved_errors(self):
        groups = {
            ("m", "neutral"): [{"scenario_id": "s1", "api_error": "timeout"}],
            ("m", "contaminated"): [{"scenario_id": "s1"}],
        }
        with self.assertRaisesRegex(ValueError, "unresolved errors"):
            validate_matrix(
                groups,
                expected_models=["m"],
                expected_framings=["neutral", "contaminated"],
                expected_per_cell=1,
            )

    def test_paired_framing_summary_uses_same_scenario_ids(self):
        rows = []
        outcomes = {
            ("attack-1", "neutral"): False,
            ("attack-1", "contaminated"): True,
            ("attack-2", "neutral"): False,
            ("attack-2", "contaminated"): False,
            ("benign-1", "neutral"): True,
            ("benign-1", "contaminated"): False,
            ("benign-2", "neutral"): True,
            ("benign-2", "contaminated"): True,
        }
        for (scenario_id, framing), approve in outcomes.items():
            rows.append(
                {
                    "model": "m",
                    "scenario_id": scenario_id,
                    "framing": framing,
                    "expected_approve": scenario_id.startswith("benign"),
                    "approve": approve,
                }
            )
        summary = paired_framing_summary(rows, ["m"])
        attack = next(row for row in summary if row["endpoint"] == "attack_false_approval")
        legitimate = next(row for row in summary if row["endpoint"] == "legitimate_approval")
        self.assertEqual(attack["n_pairs"], 2)
        self.assertEqual(attack["neutral_no_contaminated_yes"], 1)
        self.assertEqual(attack["risk_difference_contaminated_minus_neutral"], 0.5)
        self.assertEqual(legitimate["neutral_yes_contaminated_no"], 1)
        self.assertEqual(legitimate["risk_difference_contaminated_minus_neutral"], -0.5)

    def test_exact_mcnemar_and_holm_adjustment(self):
        self.assertEqual(exact_mcnemar(0, 0), 1.0)
        self.assertAlmostEqual(exact_mcnemar(6, 0), 0.03125)
        self.assertEqual(holm_adjust([0.01, 0.04, 0.5]), [0.03, 0.08, 0.5])

    def test_confirmation_power_thresholds(self):
        self.assertEqual(minimum_consistent_discordance(10, 0.05), 6)
        self.assertEqual(minimum_consistent_discordance(10, 0.05 / 6), 8)
        self.assertLess(exact_power(10, 0.3, 0.0, 0.05), 0.05)
        self.assertGreater(exact_power(30, 0.3, 0.0, 0.05 / 3), 0.8)


if __name__ == "__main__":
    unittest.main()
