import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from run_http_commit_race import CommitRaceStore, post_json, start_server


def check_payload(trial_id: str, policy: str) -> dict:
    return {
        "trial_id": trial_id,
        "policy": policy,
        "authorized_effect": {
            "tool": "cron",
            "persistence": "one-shot",
            "scope": "same",
            "target": None,
            "provenance": "user",
        },
        "checked_effect": {
            "tool": "cron",
            "persistence": "one-shot",
            "scope": "same",
            "target": None,
            "provenance": "user",
        },
        "check_context": {
            "principal": "user-primary",
            "authorization_version": 7,
            "checked_at": 100,
            "expires_at": 160,
            "confirmation_nonce": None,
        },
    }


def mutation_payload(trial_id: str) -> dict:
    return {
        "trial_id": trial_id,
        "commit_effect": {
            "tool": "cron",
            "persistence": "one-shot",
            "scope": "same",
            "target": None,
            "provenance": "user",
        },
        "commit_context": {
            "principal": "user-primary",
            "authorization_version": 8,
            "committed_at": 105,
            "confirmation_nonce": None,
            "nonce_consumed": False,
        },
        "hold_ms": 0,
    }


class HTTPCommitRaceTests(unittest.TestCase):
    def make_store(self, directory: str) -> CommitRaceStore:
        return CommitRaceStore(pathlib.Path(directory) / "sandbox.sqlite", b"k" * 32)

    def test_check_once_writes_invalid_commit_to_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            try:
                store.check(check_payload("trial", "check-once"))
                store.mutate(mutation_payload("trial"), 10)
                result = store.commit({"trial_id": "trial"}, 20)
                self.assertTrue(result["committed"])
                self.assertFalse(result["valid_at_commit"])
                self.assertEqual(result["ledger_rows"], 1)
            finally:
                store.close()

    def test_commit_bound_blocks_mutated_context(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            try:
                store.check(check_payload("trial", "commit-bound"))
                store.mutate(mutation_payload("trial"), 10)
                result = store.commit({"trial_id": "trial"}, 20)
                self.assertFalse(result["committed"])
                self.assertEqual(result["binding_decision"], "block")
                self.assertEqual(result["ledger_rows"], 0)
            finally:
                store.close()

    def test_http_check_and_valid_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            try:
                server, thread, base_url = start_server(store)
            except PermissionError:
                store.close()
                self.skipTest("sandbox forbids binding a localhost test socket")
            try:
                checked = post_json(
                    base_url, "/check", check_payload("trial", "commit-bound")
                )
                committed = post_json(base_url, "/commit", {"trial_id": "trial"})
                self.assertEqual(checked["decision"], "allow")
                self.assertTrue(committed["committed"])
                self.assertTrue(committed["valid_at_commit"])
                self.assertEqual(committed["ledger_rows"], 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                store.close()


if __name__ == "__main__":
    unittest.main()
