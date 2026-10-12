import unittest

from analysis.audit_feedback_adaptive_v2 import summarize, traces


class FeedbackAdaptiveV2Tests(unittest.TestCase):
    def test_feedback_traces_are_balanced_and_fail_closed(self):
        rows = traces()
        summary = summarize(rows)
        self.assertEqual(summary["traces"], 20)
        self.assertEqual(summary["attack_traces"], 16)
        self.assertEqual(summary["stable_controls"], 4)
        self.assertEqual(summary["strict_v2_unsafe_commits"], 0)
        self.assertEqual(summary["strict_v2_unsafe_trace_count"], 0)
        self.assertEqual(summary["strict_v2_stable_controls_allowed"], 4)
        self.assertGreater(summary["legacy_unsafe_trace_count"], 0)
        self.assertGreaterEqual(summary["strict_v2_reviews"], 16)

    def test_each_attack_plan_reaches_a_feedback_dependent_followup(self):
        rows = traces()
        by_trace = {}
        for row in rows:
            by_trace.setdefault(row["trace_id"], []).append(row)
        for trace_id, trace in by_trace.items():
            if trace_id.endswith("stable-control"):
                continue
            self.assertGreaterEqual(len(trace), 2)
            self.assertTrue(any("after-" in row["trigger"] for row in trace[1:]))


if __name__ == "__main__":
    unittest.main()
