import unittest

from formal.bounded_multi_principal_authority import audit, cases


class MultiPrincipalAuthorityTests(unittest.TestCase):
    def test_matrix_is_balanced_and_receipt_bound(self):
        rows = cases()
        summary = audit(rows)
        self.assertEqual(summary["cases"], 36)
        self.assertEqual(summary["profiles"], 9)
        self.assertEqual(summary["receipt_bound_all_expected"], 1)
        self.assertEqual(summary["cached_all_expected"], 1)
        self.assertEqual(
            summary["receipt_bound_block_reasons"],
            {
                "block-budget": 4,
                "block-principal": 4,
                "block-relation": 12,
                "block-version": 4,
            },
        )

    def test_delegation_and_partial_grants_fail_closed(self):
        rows = cases()
        stale_profiles = {
            "partial-target",
            "partial-lifetime",
            "partial-scope",
            "delegation-revoked",
            "owner-conflict",
            "budget-shrink",
        }
        stale = [row for row in rows if row["profile"] in stale_profiles]
        self.assertEqual(len(stale), 24)
        self.assertTrue(all(str(row["receipt_bound"]).startswith("block") for row in stale))
        self.assertTrue(all(row["unsafe_cached"] == 1 for row in stale))


if __name__ == "__main__":
    unittest.main()
