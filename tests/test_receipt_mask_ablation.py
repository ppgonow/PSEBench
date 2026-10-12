import unittest

from runner.run_receipt_mask_ablation import FIELDS, FIELD_TO_FAMILY, profile_for_mask


class ReceiptMaskAblationTests(unittest.TestCase):
    def test_enumerates_all_profiles(self):
        self.assertEqual(len(FIELDS), 5)
        self.assertEqual(len(FIELD_TO_FAMILY), 5)
        self.assertEqual(profile_for_mask(31), profile_for_mask(31))
        self.assertFalse(profile_for_mask(0).principal)
        self.assertFalse(profile_for_mask(0).authorization_version)
        self.assertTrue(profile_for_mask(31).confirmation_nonce)

    def test_each_single_omission_is_distinct(self):
        profiles = [profile_for_mask(31 ^ (1 << index)) for index in range(len(FIELDS))]
        self.assertEqual(len({tuple(profile.__dict__.values()) for profile in profiles}), 5)


if __name__ == "__main__":
    unittest.main()
