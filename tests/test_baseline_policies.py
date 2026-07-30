import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from baseline_policies import pfi_style, task_shield_style
from effect_boundary import EffectSpec


class BaselinePolicyTests(unittest.TestCase):
    def setUp(self):
        self.authorized = EffectSpec("cron", "one-shot")
        self.proposed = EffectSpec("cron", "recurring", provenance="untrusted")

    def test_task_shield_blocks_task_mismatch(self):
        self.assertEqual(task_shield_style(self.authorized, self.proposed).decision, "block")

    def test_pfi_blocks_untrusted_expansion(self):
        self.assertEqual(pfi_style(self.authorized, self.proposed).decision, "block")


if __name__ == "__main__":
    unittest.main()
