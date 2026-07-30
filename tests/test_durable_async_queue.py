import pathlib
import sys
import tempfile
import time
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))

from durable_async_queue import DurableAsyncQueue


class DurableAsyncQueueTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = pathlib.Path(self.temporary.name) / "broker.sqlite"
        self.queue = DurableAsyncQueue(self.database)

    def tearDown(self):
        self.temporary.cleanup()

    def dispatch(self, path, payload=None):
        return self.queue.dispatch(path, payload or {}, time.perf_counter_ns())

    def enqueue(self, trial_id, value):
        return self.dispatch(
            "/enqueue", {"trial_id": trial_id, "message": {"value": value}}
        )

    def test_fifo_claim_and_ack(self):
        first = self.enqueue("first", 1)
        second = self.enqueue("second", 2)
        self.assertLess(first["enqueue_sequence"], second["enqueue_sequence"])
        claimed = self.dispatch("/claim")
        self.assertEqual(claimed["trial_id"], "first")
        self.assertEqual(claimed["message"], {"value": 1})
        self.dispatch("/ack", {"trial_id": "first"})
        status = self.dispatch("/status", {"trial_id": "first"})
        self.assertEqual(status["state"], "acked")
        self.assertEqual(status["delivery_count"], 1)
        self.assertEqual(status["ack_count"], 1)

    def test_release_causes_at_least_once_redelivery(self):
        self.enqueue("retry", 7)
        first = self.dispatch("/claim")
        self.dispatch("/release", {"trial_id": "retry"})
        second = self.dispatch("/claim")
        self.assertEqual(first["trial_id"], second["trial_id"])
        self.assertEqual(first["message"], second["message"])
        self.assertEqual(second["delivery_number"], 2)
        self.dispatch("/ack", {"trial_id": "retry"})
        status = self.dispatch("/status", {"trial_id": "retry"})
        self.assertEqual(status["delivery_count"], 2)
        self.assertEqual(status["release_count"], 1)
        self.assertEqual(status["ack_count"], 1)

    def test_unclaimed_message_survives_broker_reopen(self):
        self.enqueue("durable", 9)
        reopened = DurableAsyncQueue(self.database)
        claimed = reopened.dispatch("/claim", {}, time.perf_counter_ns())
        self.assertEqual(claimed["trial_id"], "durable")
        self.assertEqual(claimed["message"], {"value": 9})

    def test_substitution_is_single_use_and_preclaim_only(self):
        self.enqueue("substitute", "old")
        changed = self.dispatch(
            "/substitute",
            {"trial_id": "substitute", "message": {"value": "new"}},
        )
        self.assertGreater(changed["substitution_sequence"], 0)
        with self.assertRaises(ValueError):
            self.dispatch(
                "/substitute",
                {"trial_id": "substitute", "message": {"value": "again"}},
            )
        claimed = self.dispatch("/claim")
        self.assertEqual(claimed["message"], {"value": "new"})
        with self.assertRaises(ValueError):
            self.dispatch(
                "/substitute",
                {"trial_id": "substitute", "message": {"value": "late"}},
            )


if __name__ == "__main__":
    unittest.main()
