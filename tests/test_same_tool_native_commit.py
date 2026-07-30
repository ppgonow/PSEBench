import pathlib
import secrets
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from effect_boundary import check_effect
from run_same_tool_native_commit import (
    ACTION_TOOL_NAMES,
    MODELS,
    action_tool_definition,
    load_scenarios,
    native_commit_bridge,
)
from same_tool_effects import authorized_effect, normalize_call
from service_integrated_commit import ServiceIntegratedEffect


class SameToolNativeCommitTests(unittest.TestCase):
    def test_manifest_is_balanced_and_paired(self):
        scenarios = load_scenarios(
            ROOT / "scenarios" / "same-tool-native-holdout" / "MANIFEST.csv"
        )
        self.assertEqual(len(scenarios), 96)
        self.assertEqual(len({item["template_id"] for item in scenarios}), 48)
        for template_id in {item["template_id"] for item in scenarios}:
            self.assertEqual(
                {item["exposure"] for item in scenarios if item["template_id"] == template_id},
                {"clean", "injected"},
            )

        blocks = {
            (item["carrier"], item["template_id"].rsplit("-", 1)[-1])
            for item in scenarios
        }
        self.assertEqual(len(blocks), 12)
        for carrier, cell in blocks:
            self.assertEqual(
                {
                    item["workflow"]
                    for item in scenarios
                    if item["carrier"] == carrier
                    and item["template_id"].endswith(f"-{cell}")
                },
                {"reminder", "file", "calendar", "message"},
            )

    def test_each_workflow_has_one_parameterized_action(self):
        names = {action_tool_definition(workflow)["name"] for workflow in ("reminder", "file", "calendar", "message")}
        self.assertEqual(names, ACTION_TOOL_NAMES)
        self.assertEqual(len(names), 4)

    def test_native_commit_bridge_separates_cached_and_receipt(self):
        scenario = load_scenarios(
            ROOT / "scenarios" / "same-tool-native-holdout" / "MANIFEST.csv"
        )[0]
        tool = action_tool_definition(scenario["workflow"])["name"]
        effect = normalize_call(tool, scenario["authorized_arguments"]).effect
        grant = authorized_effect(scenario["workflow"], scenario["authorized_arguments"])
        self.assertEqual(check_effect(grant, effect).decision, "allow")
        with tempfile.TemporaryDirectory() as directory:
            key = secrets.token_bytes(32)
            service = ServiceIntegratedEffect(pathlib.Path(directory) / "commit.sqlite", key)
            rows = native_commit_bridge(service, key, MODELS[0], scenario, effect)
        indexed = {(row["policy"], row["state"]): row for row in rows}
        self.assertEqual(len(indexed), 4)
        self.assertEqual(indexed[("cached-pre-action", "stable")]["committed"], 1)
        self.assertEqual(indexed[("cached-pre-action", "revoked")]["committed"], 1)
        self.assertEqual(indexed[("receipt-bound", "stable")]["committed"], 1)
        self.assertEqual(indexed[("receipt-bound", "revoked")]["committed"], 0)


if __name__ == "__main__":
    unittest.main()
