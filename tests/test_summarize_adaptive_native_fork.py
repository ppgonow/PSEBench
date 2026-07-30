import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))

from summarize_adaptive_native_fork import exact_mcnemar, group_summary, sanitize_metadata


class AdaptiveNativeForkSummaryTests(unittest.TestCase):
    def test_exact_mcnemar(self):
        self.assertAlmostEqual(exact_mcnemar(8, 0), 0.0078125)
        self.assertEqual(exact_mcnemar(0, 0), 1.0)

    def test_development_feasibility_is_per_alias(self):
        rows = []
        for index in range(16):
            unsafe = index < 4
            rows.append(
                {
                    "requested_alias": "alias-a",
                    "status": "forked" if index < 15 else "invalid_exposure",
                    "unsafe_first_proposal": unsafe,
                    "_unsafe_any_proposal": unsafe,
                    "primary_effect_proposed": not unsafe,
                    "http_attempts": 3,
                    "branches": {
                        "permissive": {
                            "attack_succeeded": unsafe,
                            "primary_effect_completed": not unsafe,
                            "sender_confirmation_calls": 1,
                        },
                        "IACG": {
                            "attack_succeeded": False,
                            "primary_effect_completed": True,
                            "sender_confirmation_calls": 1,
                        },
                    }
                    if index < 15
                    else {},
                }
            )
        summary = next(
            row for row in group_summary(rows) if row["requested_alias"] == "alias-a"
        )
        self.assertTrue(summary["development_feasible"])
        self.assertEqual(summary["valid_exposure"], 15)
        self.assertEqual(summary["unsafe_first_proposal"], 4)

    def test_sanitizing_already_hashed_metadata_is_idempotent(self):
        item = {
            "created": 1,
            "phase": "shared-prefix",
            "request_id_hash": "request-hash",
            "response_id_hash": "response-hash",
            "response_model": "alias-a",
            "service_tier": None,
            "system_fingerprint": None,
            "turn": 1,
        }
        self.assertEqual(sanitize_metadata([item]), [item])


if __name__ == "__main__":
    unittest.main()
