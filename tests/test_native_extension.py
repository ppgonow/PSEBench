import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))

from audit_native_extension import audit, load  # noqa: E402


class NativeExtensionTests(unittest.TestCase):
    def test_grok46_extension_is_recorded_as_invalid_not_rate(self):
        final = ROOT / "analysis" / "same_tool_native_commit_grok_4_6_final.jsonl"
        if not final.exists():
            self.skipTest("extension run has not been materialized")
        result = audit(
            load(final),
            "grok-4.6",
            ROOT / "analysis" / "native_extension_protocol_v1.md",
        )
        self.assertEqual(result["rows"], 96)
        self.assertEqual(result["unique_scenarios"], 96)
        self.assertEqual(result["proposal_ready"], 86)
        self.assertEqual(result["invalid_row_count"], 10)
        self.assertEqual(result["valid_for_security_rate"], 0)
        self.assertIn("do not estimate ASR/TCR", result["interpretation"])


if __name__ == "__main__":
    unittest.main()

