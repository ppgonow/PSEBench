import pathlib
import sys
import tempfile
import time
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from failover_queue import FailoverQueue


class FailoverQueueTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.queue = FailoverQueue(
            pathlib.Path(self.temporary.name) / "failover.sqlite"
        )

    def tearDown(self):
        self.temporary.cleanup()

    def dispatch(self, path, payload=None):
        return self.queue.dispatch(path, payload or {}, time.perf_counter_ns())

    def enqueue(self, trial_id, value):
        self.dispatch(
            "/enqueue", {"trial_id": trial_id, "message": {"value": value}}
        )

    def test_recover_owner_redelivers_to_new_consumer(self):
        self.enqueue("one", 1)
        first = self.dispatch("/claim", {"owner": "consumer-a"})
        self.assertEqual(first["delivery_number"], 1)
        recovered = self.dispatch("/recover-owner", {"owner": "consumer-a"})
        self.assertEqual(recovered["recovered"], 1)
        second = self.dispatch("/claim", {"owner": "consumer-b"})
        self.assertEqual(second["trial_id"], "one")
        self.assertEqual(second["delivery_number"], 2)
        self.dispatch("/ack", {"trial_id": "one", "owner": "consumer-b"})
        status = self.dispatch("/status", {"trial_id": "one"})
        self.assertEqual(status["state"], "acked")
        self.assertEqual(status["recovery_count"], 1)

    def test_wrong_owner_cannot_ack(self):
        self.enqueue("owned", 2)
        self.dispatch("/claim", {"owner": "consumer-a"})
        with self.assertRaises(ValueError):
            self.dispatch("/ack", {"trial_id": "owned", "owner": "consumer-b"})

    def test_recovery_is_scoped_to_failed_owner(self):
        self.enqueue("a", 1)
        self.enqueue("b", 2)
        self.dispatch("/claim", {"owner": "consumer-a"})
        self.dispatch("/claim", {"owner": "consumer-b"})
        recovered = self.dispatch("/recover-owner", {"owner": "consumer-a"})
        self.assertEqual(recovered["recovered"], 1)
        status_a = self.dispatch("/status", {"trial_id": "a"})
        status_b = self.dispatch("/status", {"trial_id": "b"})
        self.assertEqual(status_a["state"], "queued")
        self.assertEqual(status_b["state"], "inflight")

    def test_substitution_is_rejected_after_claim(self):
        self.enqueue("sub", "old")
        self.dispatch("/claim", {"owner": "consumer-a"})
        with self.assertRaises(ValueError):
            self.dispatch(
                "/substitute",
                {"trial_id": "sub", "message": {"value": "new"}},
            )


if __name__ == "__main__":
    unittest.main()
