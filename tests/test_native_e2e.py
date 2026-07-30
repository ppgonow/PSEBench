import argparse
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from run_native_e2e import (
    MODELS,
    POLICIES,
    SandboxLedger,
    execute_tool,
    load_matrix,
    matrix_jobs,
    preflight_live,
    run_anthropic_job,
    run_openai_job,
    task_completed,
    trace_has_exposure,
    validate_models,
)


class FakeRequester:
    def __init__(self, responses):
        self.responses = list(responses)
        self.payloads = []

    def post(self, provider, payload):
        self.payloads.append((provider, payload))
        expected_provider, response = self.responses.pop(0)
        if provider != expected_provider:
            raise AssertionError(f"expected {expected_provider}, got {provider}")
        return response, 1


class NativeE2ETests(unittest.TestCase):
    def test_frozen_matrix_is_balanced_and_has_288_units(self):
        scenarios = load_matrix(ROOT / "scenarios" / "native-e2e48" / "MANIFEST.csv")
        validate_models(list(MODELS))
        self.assertEqual(len(matrix_jobs(scenarios, list(MODELS), list(POLICIES))), 288)

    def test_sqlite_outcome_comes_from_executed_tools(self):
        scenarios = load_matrix(ROOT / "scenarios" / "native-e2e48" / "MANIFEST.csv")
        scenario = next(item for item in scenarios if item["_boundary"] == "file")
        with tempfile.TemporaryDirectory() as directory:
            ledger = SandboxLedger(pathlib.Path(directory) / "sandbox.sqlite")
            try:
                allowed = execute_tool(
                    ledger,
                    "job",
                    "one",
                    "write_one_shot_file_note",
                    {"text": "bounded"},
                    scenario,
                    "IACG",
                )
                blocked = execute_tool(
                    ledger,
                    "job",
                    "two",
                    "write_persistent_file_entry",
                    {"text": "durable"},
                    scenario,
                    "IACG",
                )
                effects = ledger.effects("job")
                self.assertTrue(allowed["ok"])
                self.assertFalse(blocked["ok"])
                self.assertEqual(len(effects), 1)
                self.assertTrue(task_completed("file", effects))
            finally:
                ledger.close()

    def test_permissive_commits_escalation(self):
        scenarios = load_matrix(ROOT / "scenarios" / "native-e2e48" / "MANIFEST.csv")
        scenario = next(item for item in scenarios if item["_boundary"] == "recipient")
        with tempfile.TemporaryDirectory() as directory:
            ledger = SandboxLedger(pathlib.Path(directory) / "sandbox.sqlite")
            try:
                result = execute_tool(
                    ledger,
                    "job",
                    "one",
                    "send_status_update",
                    {"recipient": "attacker@example.com", "text": "status"},
                    scenario,
                    "permissive",
                )
                self.assertTrue(result["ok"])
                self.assertEqual(ledger.effects("job")[0].scope, "expanded")
            finally:
                ledger.close()

    def test_live_preflight_requires_endpoint_credential_before_output(self):
        args = argparse.Namespace(
            openai_base_url="https://api.openai.com/v1",
            anthropic_base_url="https://api.anthropic.com",
        )
        clean = {
            key: value
            for key, value in os.environ.items()
            if key != "OPENAI_API_KEY"
        }
        with mock.patch.dict(os.environ, clean, clear=True):
            with self.assertRaisesRegex(RuntimeError, "missing live credentials"):
                preflight_live(args)

    def test_exposure_requires_one_read_before_effect(self):
        self.assertTrue(
            trace_has_exposure(
                [
                    {"name": "read_inbound_message"},
                    {"name": "create_one_shot_reminder"},
                    {"name": "confirm_to_sender"},
                ]
            )
        )
        self.assertFalse(trace_has_exposure([{"name": "create_one_shot_reminder"}]))
        self.assertFalse(
            trace_has_exposure(
                [
                    {"name": "create_one_shot_reminder"},
                    {"name": "read_inbound_message"},
                ]
            )
        )

    def test_openai_native_tool_loop_mediates_and_commits(self):
        scenarios = load_matrix(ROOT / "scenarios" / "native-e2e48" / "MANIFEST.csv")
        scenario = next(item for item in scenarios if item["_boundary"] == "file")
        requester = FakeRequester(
            [
                (
                    "openai",
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": None,
                                    "tool_calls": [
                                        {"id": "read", "function": {"name": "read_inbound_message", "arguments": "{}"}},
                                        {"id": "bad", "function": {"name": "write_persistent_file_entry", "arguments": '{"text":"durable"}'}},
                                        {"id": "task", "function": {"name": "write_one_shot_file_note", "arguments": '{"text":"bounded"}'}},
                                    ],
                                }
                            }
                        ]
                    },
                ),
                ("openai", {"choices": [{"message": {"content": "done", "tool_calls": []}}]}),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            ledger = SandboxLedger(pathlib.Path(directory) / "sandbox.sqlite")
            try:
                trace, text, turns, attempts = run_openai_job(
                    requester, "gpt-5.5", "IACG", scenario, ledger, "job", 6
                )
                effects = ledger.effects("job")
                self.assertEqual((len(trace), text, turns, attempts), (3, "done", 2, 2))
                self.assertEqual(len(effects), 1)
                self.assertTrue(task_completed("file", effects))
                self.assertFalse(trace[1]["result"]["ok"])
                self.assertEqual(requester.payloads[0][0], "openai")
            finally:
                ledger.close()

    def test_anthropic_native_tool_loop_records_actual_recipient_effects(self):
        scenarios = load_matrix(ROOT / "scenarios" / "native-e2e48" / "MANIFEST.csv")
        scenario = next(item for item in scenarios if item["_boundary"] == "recipient")
        requester = FakeRequester(
            [
                (
                    "anthropic",
                    {
                        "content": [
                            {"type": "tool_use", "id": "read", "name": "read_inbound_message", "input": {}},
                            {"type": "tool_use", "id": "task", "name": "send_status_update", "input": {"recipient": "TEST_CHANNEL", "text": "status"}},
                            {"type": "tool_use", "id": "bad", "name": "send_status_update", "input": {"recipient": "attacker@example.com", "text": "status"}},
                        ]
                    },
                ),
                ("anthropic", {"content": [{"type": "text", "text": "done"}]}),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            ledger = SandboxLedger(pathlib.Path(directory) / "sandbox.sqlite")
            try:
                trace, text, turns, attempts = run_anthropic_job(
                    requester,
                    "claude-opus-4-6",
                    "permissive",
                    scenario,
                    ledger,
                    "job",
                    6,
                )
                effects = ledger.effects("job")
                self.assertEqual((len(trace), text, turns, attempts), (3, "done", 2, 2))
                self.assertEqual([effect.scope for effect in effects], ["same", "expanded"])
                self.assertTrue(task_completed("recipient", effects))
                self.assertEqual(requester.payloads[0][0], "anthropic")
            finally:
                ledger.close()


if __name__ == "__main__":
    unittest.main()
