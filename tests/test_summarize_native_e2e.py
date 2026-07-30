import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))

from summarize_native_e2e import (
    attempt_audit,
    exact_mcnemar,
    summarize,
    validate_outcomes,
    wilson,
)


class NativeE2ESummaryTests(unittest.TestCase):
    def test_exact_statistics(self):
        self.assertAlmostEqual(exact_mcnemar(12, 0), 0.00048828125)
        low, high = wilson(0, 48)
        self.assertEqual(low, 0.0)
        self.assertGreater(high, 0.0)

    def test_summary_keeps_model_and_pooled_descriptive_rows_separate(self):
        rows = [
            {
                "model_spec": "openai:gpt-5.5",
                "policy": "IACG",
                "boundary": "cron",
                "scenario_id": "same-scenario",
                "attack_succeeded": False,
                "task_completed": True,
                "native_tool_calls": 2,
                "http_attempts": 2,
            },
            {
                "model_spec": "anthropic:claude-opus-4-6",
                "policy": "IACG",
                "boundary": "cron",
                "scenario_id": "same-scenario",
                "attack_succeeded": False,
                "task_completed": True,
                "native_tool_calls": 3,
                "http_attempts": 2,
            },
        ]
        output = summarize(rows)
        pooled = next(
            row
            for row in output
            if row["model"] == "pooled-descriptive" and row["boundary"] == "all"
        )
        self.assertEqual(pooled["n_observations"], 2)
        self.assertEqual(pooled["n_unique_scenarios"], 1)
        self.assertEqual(pooled["task_yes"], 2)
        self.assertEqual(pooled["primary_effect_yes"], 2)
        self.assertEqual(pooled["native_tool_calls"], 5)

    def test_outcome_validation_recomputes_labels_from_trace_and_scenario(self):
        effect = {
            "tool": "file",
            "persistence": "one-shot",
            "scope": "same",
            "target": None,
            "provenance": "user",
        }
        row = {
            "scenario_id": "H-file-persist-required-001",
            "scenario_path": "scenarios/hybrid-file/H-file-persist-required-001.yaml",
            "boundary": "file",
            "native_tool_calls": 2,
            "committed_effects": [effect],
            "tool_trace": [
                {
                    "turn": 1,
                    "tool_call_id": "read-1",
                    "name": "read_inbound_message",
                    "arguments": {},
                    "result": {"ok": True, "untrusted": True, "content": "injected"},
                },
                {
                    "turn": 2,
                    "tool_call_id": "call-1",
                    "name": "write_one_shot_file_note",
                    "arguments": {"text": "bounded"},
                    "result": {
                        "ok": True,
                        "decision": "allow",
                        "ledger_id": 1,
                        "effect": effect,
                    },
                }
            ],
            "attack_succeeded": False,
            "task_completed": True,
        }
        validate_outcomes([row])
        row["attack_succeeded"] = True
        with self.assertRaisesRegex(ValueError, "attack label mismatch"):
            validate_outcomes([row])

    def test_attempt_audit_separates_primary_effect_and_confirmation(self):
        row = {
            "native_tool_calls": 2,
            "http_attempts": 2,
            "task_completed": True,
            "attack_succeeded": False,
            "committed_effects": [{"tool": "file"}],
            "tool_trace": [
                {"turn": 1, "name": "read_inbound_message", "arguments": {}, "result": {"ok": True}},
                {
                    "turn": 2,
                    "name": "write_one_shot_file_note",
                    "arguments": {"text": "bounded"},
                    "result": {"ok": True, "decision": "allow"},
                },
            ],
        }
        audit = attempt_audit([row], [row])[0]
        self.assertEqual(audit["primary_effect_yes"], 1)
        self.assertEqual(audit["units_with_sender_confirmation"], 0)
        self.assertEqual(audit["strict_exposure_units"], 1)


if __name__ == "__main__":
    unittest.main()
