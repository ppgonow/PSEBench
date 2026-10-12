import unittest

from formal.bounded_security_model import (
    run_field_matrix,
    run_receipt_minimality,
    run_interleavings,
    run_proposal_only_limit,
    run_sequence_matrix,
)


class BoundedSecurityModelTest(unittest.TestCase):
    def test_full_receipt_blocks_mutations_and_is_idempotent(self):
        result = run_field_matrix()["full"]
        self.assertEqual(result["unsafe_commits"], 0)
        self.assertEqual(result["stable_commit"], 1)
        self.assertEqual(result["duplicate_new_row"], 0)
        self.assertEqual(result["effect_rows_after_duplicate"], 1)

    def test_each_receipt_field_has_a_bounded_counterexample(self):
        result = run_field_matrix()
        for field in ("principal", "version", "effect", "expiry", "nonce"):
            self.assertEqual(result[f"without-{field}"]["unsafe_commits"], 1)

    def test_each_omission_has_only_its_matching_mutation_witness(self):
        result = run_receipt_minimality()
        for field in ("principal", "version", "effect", "expiry", "nonce"):
            self.assertEqual(result[field]["unsafe_witnesses"], [field])
            self.assertEqual(result[field]["matching_witness"], 1)

    def test_linearization_and_sequence_budget_checks(self):
        self.assertEqual(run_interleavings()["mutate-before-commit-unsafe"], 0)
        sequences = run_sequence_matrix()
        self.assertEqual(sequences["cases"], 28)
        self.assertEqual(sequences["full_unsafe_commits"], 0)
        self.assertEqual(sequences["without_budget_unsafe_commits"], 3)
        self.assertEqual(sequences["concurrent_budget_overflow_witness"], 1)

    def test_proposal_only_cannot_preserve_stable_commit_and_revocation_safety(self):
        result = run_proposal_only_limit()
        self.assertEqual(result["proposal_views_equal"], 1)
        self.assertEqual(result["cached_stable_commit"], 1)
        self.assertEqual(result["cached_revoked_unsafe"], 1)
        self.assertEqual(result["always_block_stable_commit"], 0)
        self.assertEqual(result["receipt_stable_commit"], 1)
        self.assertEqual(result["receipt_revoked_commit"], 0)
