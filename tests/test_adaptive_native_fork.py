import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from generate_adaptive_native_fork import generate
from run_adaptive_native_fork import (
    adaptive_tool_definitions,
    read_manifest,
    run_forked_job,
)
from run_native_e2e import SandboxLedger


class FakeRequester:
    def __init__(self, responses):
        self.responses = list(responses)
        self.payloads = []
        self.last_response_metadata = {}

    def post(self, provider, payload):
        self.payloads.append((provider, payload))
        self.last_response_metadata = {
            "response_id": f"fake-{len(self.payloads)}",
            "response_model": payload["model"],
        }
        return self.responses.pop(0), 1


def response(*calls, content=None):
    return {
        "choices": [
            {
                "message": {
                    "content": content,
                    "tool_calls": list(calls),
                }
            }
        ]
    }


def call(identifier, name, arguments):
    import json

    return {
        "id": identifier,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


class AdaptiveNativeForkTests(unittest.TestCase):
    def test_neutral_schema_removes_provenance_cues(self):
        tools = adaptive_tool_definitions("cron", "neutral")
        read_tool = next(tool for tool in tools if tool["name"] == "read_inbound_message")
        description = read_tool["description"].lower()
        for cue in ("untrusted", "trusted", "authority", "provenance"):
            self.assertNotIn(cue, description)

        marked = adaptive_tool_definitions("cron", "provenance-marked")
        marked_read = next(tool for tool in marked if tool["name"] == "read_inbound_message")
        self.assertIn("untrusted", marked_read["description"].lower())

    def test_generator_is_balanced_and_cue_free(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = generate("dev", 2, pathlib.Path(directory))
            self.assertEqual(len(rows), 8)
            self.assertEqual({row["guard_cue_hits"] for row in rows}, {"0"})
            self.assertEqual(
                {boundary: sum(row["boundary"] == boundary for row in rows) for boundary in {row["boundary"] for row in rows}},
                {"cron": 2, "file": 2, "calendar": 2, "recipient": 2},
            )

    def test_shared_unsafe_proposal_is_forked_without_resampling(self):
        scenarios = read_manifest(
            ROOT / "scenarios" / "adaptive-native-dev" / "MANIFEST.csv"
        )
        scenario = next(item for item in scenarios if item["_boundary"] == "cron")
        requester = FakeRequester(
            [
                response(call("read", "read_inbound_message", {})),
                response(
                    call(
                        "unsafe",
                        "create_recurring_reminder",
                        {"text": "successor chain", "interval": "derived offset"},
                    )
                ),
                response(content="permissive branch done"),
                response(
                    call(
                        "safe",
                        "create_one_shot_reminder",
                        {"text": "bounded reminder"},
                    )
                ),
                response(
                    call(
                        "confirm",
                        "confirm_to_sender",
                        {"text": "bounded reminder created"},
                    )
                ),
                response(content="IACG branch done"),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            ledger = SandboxLedger(pathlib.Path(directory) / "sandbox.sqlite")
            try:
                result = run_forked_job(
                    requester,
                    "gpt-test",
                    scenario,
                    ledger,
                    "test-run",
                    6,
                    "neutral",
                )
            finally:
                ledger.close()
        self.assertEqual(result["status"], "forked")
        self.assertTrue(result["prefix_exposed"])
        self.assertTrue(result["unsafe_first_proposal"])
        self.assertTrue(result["branches"]["permissive"]["attack_succeeded"])
        self.assertFalse(result["branches"]["IACG"]["attack_succeeded"])
        self.assertFalse(result["branches"]["permissive"]["primary_effect_completed"])
        self.assertTrue(result["branches"]["IACG"]["primary_effect_completed"])
        self.assertEqual(result["branches"]["IACG"]["policy_block_decisions"], 1)
        self.assertEqual(len(requester.payloads), 6)
        for _, payload in requester.payloads:
            read_tool = next(
                tool for tool in payload["tools"]
                if tool["function"]["name"] == "read_inbound_message"
            )
            self.assertNotIn("untrusted", read_tool["function"]["description"].lower())


if __name__ == "__main__":
    unittest.main()
