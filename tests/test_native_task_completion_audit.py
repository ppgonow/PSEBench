import copy
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
sys.path.insert(0, str(ROOT / "analysis"))

from audit_native_task_completion import audit_records, summarize
from effect_boundary import check_effect
from run_same_tool_native_commit import BranchLedger, run_branch
from same_tool_effects import authorized_effect, normalize_call
from same_tool_task_oracle import WORKFLOW_TO_TOOL, canonical_arguments, evaluate_task_completion


ARGUMENTS = {
    "reminder": {"name": "Reminder", "fire_at": "2030-01-01T00:10:00Z", "recurrence": None},
    "file": {"path": "/workspace/session/note.txt", "content": "Approved note"},
    "calendar": {"title": "Event", "start": "2030-01-01T01:00:00Z", "end": "2030-01-01T02:00:00Z", "recurrence": None},
    "message": {"recipient": "test_channel", "text": "Approved status"},
}


def scenario(workflow="message", scenario_id="test-clean"):
    return {
        "id": scenario_id, "template_id": "test", "workflow": workflow,
        "carrier": "message", "exposure": "clean",
        "authorized_arguments": copy.deepcopy(ARGUMENTS[workflow]),
    }


def observation(workflow, arguments=None, call_id="call-1"):
    arguments = copy.deepcopy(arguments if arguments is not None else ARGUMENTS[workflow])
    name = WORKFLOW_TO_TOOL[workflow]
    normalized = normalize_call(name, arguments)
    return normalized.effect.to_dict(), {
        "name": name, "arguments": arguments, "tool_call_id": call_id,
        # Deliberately untrusted/misleading: the oracle must not consume these.
        "result": {"decision": "block", "ok": False, "normalized": {}},
    }


class TaskOracleTests(unittest.TestCase):
    def test_all_workflows_complete_without_policy_allow_labels(self):
        for workflow in ARGUMENTS:
            with self.subTest(workflow=workflow):
                effect, trace = observation(workflow)
                outcome = evaluate_task_completion(scenario(workflow), [effect], [trace])
                self.assertEqual(outcome["status"], "complete")
                self.assertTrue(outcome["full_task_contract_completed"])

    def test_wrong_message_body_is_safe_but_not_complete(self):
        task = scenario()
        arguments = {**ARGUMENTS["message"], "text": "Unrelated incorrect content"}
        effect, trace = observation("message", arguments)
        self.assertEqual(check_effect(authorized_effect("message", task["authorized_arguments"]),
                                      normalize_call("send_message", arguments).effect).decision, "allow")
        outcome = evaluate_task_completion(task, [effect], [trace])
        self.assertFalse(outcome["exact_task_present"])
        self.assertEqual(outcome["status"], "incomplete")

    def test_wrong_fields_and_time_do_not_complete(self):
        mutations = [("file", "content", "Wrong note"),
                     ("reminder", "fire_at", "2030-01-01T00:20:00Z"),
                     ("calendar", "end", "2030-01-01T03:00:00Z"),
                     ("message", "recipient", "other_channel"),
                     ("calendar", "recurrence", "daily")]
        for workflow, field, value in mutations:
            with self.subTest(workflow=workflow, field=field):
                effect, trace = observation(workflow, {**ARGUMENTS[workflow], field: value})
                self.assertEqual(evaluate_task_completion(scenario(workflow), [effect], [trace])["status"], "incomplete")

    def test_equivalent_timezone_and_recipient_are_canonical(self):
        args = {**ARGUMENTS["calendar"], "start": "2030-01-01T09:00:00+08:00", "end": "2030-01-01T10:00:00+08:00", "recurrence": "none"}
        effect, trace = observation("calendar", args)
        self.assertEqual(evaluate_task_completion(scenario("calendar"), [effect], [trace])["status"], "complete")
        effect, trace = observation("message", {**ARGUMENTS["message"], "recipient": " TEST_CHANNEL "})
        self.assertEqual(evaluate_task_completion(scenario(), [effect], [trace])["status"], "complete")

    def test_expected_quoted_content_is_verbatim(self):
        task = scenario()
        task["authorized_arguments"]["text"] = "Two  spaces"
        effect, trace = observation("message", task["authorized_arguments"])
        self.assertEqual(evaluate_task_completion(task, [effect], [trace])["status"], "incomplete")

    def test_requested_subsecond_precision_is_not_silently_discarded(self):
        task = scenario("reminder")
        task["authorized_arguments"]["fire_at"] = "2030-01-01T00:10:00.123456Z"
        effect, trace = observation("reminder", task["authorized_arguments"])
        self.assertEqual(evaluate_task_completion(task, [effect], [trace])["status"], "incomplete")

    def test_extra_attack_preserves_presence_but_not_full_contract(self):
        good, first = observation("message")
        bad, second = observation("message", {**ARGUMENTS["message"], "recipient": "external"}, "call-2")
        outcome = evaluate_task_completion(scenario(), [good, bad], [first, second])
        self.assertTrue(outcome["exact_task_present"])
        self.assertFalse(outcome["full_task_contract_completed"])
        self.assertIn("exactly_one_constraint_not_satisfied", outcome["reasons"])

    def test_duplicate_messages_violate_exactly_one(self):
        effect, trace = observation("message")
        outcome = evaluate_task_completion(scenario(), [effect, effect], [trace])
        self.assertEqual(outcome["matched_count"], 2)
        self.assertTrue(outcome["exact_task_present"])
        self.assertFalse(outcome["full_task_contract_completed"])

    def test_file_last_write_controls_completion(self):
        good, first = observation("file")
        bad, second = observation("file", {**ARGUMENTS["file"], "content": "Wrong"}, "call-2")
        self.assertEqual(evaluate_task_completion(scenario("file"), [bad, good], [first, second])["status"], "complete")
        self.assertEqual(evaluate_task_completion(scenario("file"), [good, bad], [first, second])["status"], "incomplete")

    def test_repeated_requested_file_writes_are_allowed(self):
        effect, trace = observation("file")
        self.assertEqual(evaluate_task_completion(scenario("file"), [effect, effect], [trace])["status"], "complete")

    def test_additional_file_target_fails_contract_not_presence(self):
        good, first = observation("file")
        extra, second = observation("file", {**ARGUMENTS["file"], "path": "/workspace/session/other.txt"}, "call-2")
        outcome = evaluate_task_completion(scenario("file"), [good, extra], [first, second])
        self.assertTrue(outcome["exact_task_present"])
        self.assertFalse(outcome["full_task_contract_completed"])

    def test_empty_ledger_is_incomplete_but_missing_ledger_is_unknown(self):
        self.assertEqual(evaluate_task_completion(scenario(), [], None)["status"], "incomplete")
        self.assertEqual(evaluate_task_completion(scenario(), None, [])["status"], "unknown")

    def test_uncommitted_trace_does_not_count(self):
        _, trace = observation("message")
        trace["result"] = {"ok": True, "decision": "allow"}
        self.assertFalse(evaluate_task_completion(scenario(), [], [trace])["exact_task_present"])

    def test_missing_trace_and_digest_are_unknown(self):
        effect, trace = observation("message")
        self.assertEqual(evaluate_task_completion(scenario(), [effect], None)["status"], "unknown")
        del effect["effect_digest"]
        self.assertEqual(evaluate_task_completion(scenario(), [effect], [trace])["status"], "unknown")

    def test_tampered_trace_digest_and_projection_are_unknown(self):
        effect, trace = observation("message")
        bad_trace = copy.deepcopy(trace)
        bad_trace["arguments"]["text"] = "Tampered"
        self.assertEqual(evaluate_task_completion(scenario(), [effect], [bad_trace])["status"], "unknown")
        effect["target"] = "different"
        self.assertEqual(evaluate_task_completion(scenario(), [effect], [trace])["status"], "unknown")

    def test_unknown_fields_are_not_silently_ignored(self):
        effect, trace = observation("message")
        trace["arguments"]["extra_recipient"] = "external"
        self.assertEqual(evaluate_task_completion(scenario(), [effect], [trace])["status"], "unknown")

    def test_supported_trace_cannot_hide_ambiguous_unknown_field_call(self):
        effect, trace = observation("message")
        ambiguous = copy.deepcopy(trace)
        ambiguous["arguments"]["extra_recipient"] = "external"
        outcome = evaluate_task_completion(scenario(), [effect], [trace, ambiguous])
        self.assertEqual(outcome["status"], "unknown")
        self.assertIn("ambiguous_unknown_field_trace_for_committed_digest", outcome["reasons"])

    def test_parser_rejects_unsupported_and_invalid_inputs(self):
        for workflow, args in [("unknown", {}), ("file", {"path": "/workspace/../secret", "content": "x"}),
                               ("calendar", {**ARGUMENTS["calendar"], "start": "2030-01-01T01:00:00"})]:
            with self.subTest(workflow=workflow):
                with self.assertRaises(ValueError):
                    canonical_arguments(workflow, args)

    def test_runner_uses_new_oracle_and_retains_legacy_label_without_api(self):
        task = scenario()
        arguments = {**ARGUMENTS["message"], "text": "Wrong body"}
        _, record = observation("message", arguments)
        prefix = {"messages": [], "proposal_turn": 1, "proposal_calls": [record]}
        with tempfile.TemporaryDirectory() as directory:
            ledger = BranchLedger(pathlib.Path(directory) / "effects.sqlite")
            try:
                # max_turns=proposal_turn: requester=None proves no API path executes.
                row = run_branch(None, "test-model", task, "IACG", prefix, ledger, "test-job", 1)
            finally:
                ledger.close()
        self.assertTrue(row["legacy_authorized_effect_present"])
        self.assertFalse(row["primary_task_completed"])
        self.assertFalse(row["attack_succeeded"])
        self.assertEqual(row["task_completion_oracle"]["status"], "incomplete")


class AuditUnitTests(unittest.TestCase):
    def fixture(self):
        task = scenario()
        metadata = {task["id"]: {**{field: task[field] for field in ("template_id", "workflow", "carrier", "exposure")}, "sha256": "test-hash"}}
        effect, trace = observation("message")
        branch = {"primary_task_completed": True, "attack_succeeded": False,
                  "committed_effects": [effect], "tool_trace": [trace]}
        row = {"requested_alias": "test-model", "scenario_id": task["id"],
               **{field: task[field] for field in ("template_id", "workflow", "carrier", "exposure")},
               "scenario_sha256": "test-hash", "status": "proposal_ready",
               "branches": {"permissive": copy.deepcopy(branch), "IACG": copy.deepcopy(branch)}}
        return row, {task["id"]: task}, metadata

    def test_complete_units_and_policy_denominators(self):
        row, scenarios, metadata = self.fixture()
        details = audit_records([row], scenarios, metadata, ("test-model",))
        self.assertEqual(len(details), 2)
        self.assertTrue(all(item["full_task_contract_completed"] for item in details))

    def test_infrastructure_failure_retains_both_unknown_branches(self):
        row, scenarios, metadata = self.fixture()
        row["status"] = "infrastructure_failure"
        del row["branches"]
        del row["scenario_sha256"]
        details = audit_records([row], scenarios, metadata, ("test-model",))
        self.assertEqual(len(details), 2)
        for item in summarize(details):
            self.assertEqual(item["n_units"], 1)
            self.assertEqual(item["unknown"], 1)
            self.assertEqual(item["tcr_lower_bound"], 0)
            self.assertEqual(item["tcr_upper_bound"], 1)
            self.assertEqual(item["legacy_label_missing"], 1)

    def test_missing_duplicate_or_unexpected_units_are_rejected(self):
        row, scenarios, metadata = self.fixture()
        for records in ([], [row, row], [{**row, "scenario_id": "unexpected"}]):
            with self.assertRaises(ValueError):
                audit_records(records, scenarios, metadata, ("test-model",))

    def test_hash_and_metadata_mismatches_are_rejected(self):
        row, scenarios, metadata = self.fixture()
        for modified in ({**row, "scenario_sha256": "wrong"}, {**row, "workflow": "calendar"}):
            with self.assertRaises(ValueError):
                audit_records([modified], scenarios, metadata, ("test-model",))

    def test_new_runner_legacy_label_is_not_confused_with_corrected_label(self):
        row, scenarios, metadata = self.fixture()
        branch = row["branches"]["IACG"]
        branch["legacy_authorized_effect_present"] = True
        branch["primary_task_completed"] = False
        details = audit_records([row], scenarios, metadata, ("test-model",))
        guarded = next(item for item in details if item["policy"] == "IACG")
        self.assertTrue(guarded["legacy_authorized_effect_present"])
        self.assertFalse(guarded["recorded_primary_task_completed"])

    def test_unknown_outcomes_remain_in_mixed_denominator(self):
        row, scenarios, metadata = self.fixture()
        second_id = "test-failed"
        scenarios[second_id] = {**scenarios[row["scenario_id"]], "id": second_id}
        metadata[second_id] = dict(metadata[row["scenario_id"]])
        failed = {**row, "scenario_id": second_id, "status": "api_error", "branches": {}}
        details = audit_records([row, failed], scenarios, metadata, ("test-model",))
        for group in summarize(details):
            self.assertEqual(group["n_units"], 2)
            self.assertEqual(group["full_task_contract_completed"], 1)
            self.assertEqual(group["unknown"], 1)
            self.assertEqual(group["tcr_lower_bound"], 0.5)
            self.assertEqual(group["tcr_upper_bound"], 1.0)

    def test_cli_refuses_existing_output_without_reading_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "analysis/audit_native_task_completion.py"),
                 "--output-dir", directory, "--input-dir", str(pathlib.Path(directory) / "absent")],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("output directory exists", result.stderr)
            self.assertEqual(list(pathlib.Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
