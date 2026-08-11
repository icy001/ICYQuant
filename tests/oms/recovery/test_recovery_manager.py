"""Tests for RecoveryManager — recovery job management."""

import unittest

from services.oms.recovery.recovery_manager import RecoveryManager
from services.oms.recovery.recovery_state import RecoveryState
from services.oms.recovery.recovery_policy import RecoveryPolicy
from services.oms.recovery.recovery_result import RecoveryJob


class TestRecoveryManager(unittest.TestCase):

    def setUp(self):
        self.manager = RecoveryManager(RecoveryPolicy(max_attempts=3))

    def test_create_job(self):
        job = self.manager.create_job("ORD-001", "ACK_TIMEOUT")
        self.assertEqual(job.order_id, "ORD-001")
        self.assertEqual(job.trigger, "ACK_TIMEOUT")
        self.assertEqual(job.state, RecoveryState.PENDING)

    def test_idempotent_job(self):
        job1 = self.manager.create_job("ORD-001")
        job2 = self.manager.create_job("ORD-001")
        self.assertEqual(job1.recovery_id, job2.recovery_id)

    def test_execute_recovery_success(self):
        def query_fn(order_id):
            return {"status": "FILLED", "executed_quantity": 1000}

        job = self.manager.execute_recovery("ORD-001", query_fn)
        self.assertTrue(job.state.is_success)
        self.assertEqual(job.result["status"], "FILLED")

    def test_execute_recovery_unknown_stays_failed(self):
        def query_fn(order_id):
            return {"status": "UNKNOWN"}

        job = self.manager.execute_recovery("ORD-001", query_fn)
        self.assertFalse(job.state.is_success)
        self.assertEqual(job.attempt, 3)  # max_attempts

    def test_execute_recovery_with_exception(self):
        def query_fn(order_id):
            raise ConnectionError("timeout")

        job = self.manager.execute_recovery("ORD-001", query_fn)
        self.assertFalse(job.state.is_success)

    def test_get_active_jobs(self):
        self.manager.create_job("ORD-001")
        self.manager.create_job("ORD-002")
        active = self.manager.get_active_jobs()
        self.assertEqual(len(active), 2)


class TestRecoveryJob(unittest.TestCase):

    def test_job_lifecycle(self):
        job = RecoveryJob(order_id="ORD-001", trigger="TIMEOUT")
        self.assertEqual(job.state, RecoveryState.PENDING)

        job.start()
        self.assertEqual(job.state, RecoveryState.RUNNING)

        job.mark_recovered({"status": "FILLED"})
        self.assertEqual(job.state, RecoveryState.RECOVERED)
        self.assertTrue(job.is_terminal)

    def test_can_retry(self):
        job = RecoveryJob(order_id="ORD-001", max_attempts=3)
        self.assertTrue(job.can_retry)
        job.record_attempt()
        job.record_attempt()
        job.record_attempt()
        self.assertFalse(job.can_retry)


if __name__ == '__main__':
    unittest.main()
