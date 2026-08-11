"""Tests for TimeoutManager — timeout tracking and detection."""

import unittest
import time

from services.oms.timeout.timeout_policy import TimeoutPolicy
from services.oms.timeout.timeout_manager import (
    TimeoutManager, TimeoutType,
)


class TestTimeoutManager(unittest.TestCase):

    def setUp(self):
        self.policy = TimeoutPolicy(
            submission_timeout=0.05,  # 50ms for testing
            ack_timeout=0.05,
            cancel_timeout=0.05,
        )
        self.manager = TimeoutManager(self.policy)

    def test_start_and_cancel(self):
        self.manager.start("ORD-001", TimeoutType.SUBMISSION)
        self.manager.cancel("ORD-001", TimeoutType.SUBMISSION)
        self.assertFalse(
            self.manager.check_expired("ORD-001", TimeoutType.SUBMISSION)
        )

    def test_timeout_expired(self):
        self.manager.start("ORD-001", TimeoutType.ACK)
        time.sleep(0.06)  # wait for timeout
        self.assertTrue(
            self.manager.check_expired("ORD-001", TimeoutType.ACK)
        )

    def test_timeout_not_yet_expired(self):
        self.manager.start("ORD-001", TimeoutType.SUBMISSION)
        self.assertFalse(
            self.manager.check_expired("ORD-001", TimeoutType.SUBMISSION)
        )

    def test_check_all_expired(self):
        self.manager.start("ORD-001", TimeoutType.ACK)
        self.manager.start("ORD-002", TimeoutType.ACK)
        time.sleep(0.06)
        expired = self.manager.check_all_expired()
        self.assertEqual(len(expired), 2)

    def test_clear(self):
        self.manager.start("ORD-001", TimeoutType.SUBMISSION)
        self.manager.start("ORD-001", TimeoutType.ACK)
        self.manager.clear("ORD-001")
        self.assertIsNone(
            self.manager.get_record("ORD-001", TimeoutType.SUBMISSION)
        )
        self.assertIsNone(
            self.manager.get_record("ORD-001", TimeoutType.ACK)
        )


class TestTimeoutPolicy(unittest.TestCase):

    def test_default(self):
        policy = TimeoutPolicy.default()
        self.assertEqual(policy.submission_timeout, 5.0)

    def test_fast_market(self):
        policy = TimeoutPolicy.fast_market()
        self.assertLess(policy.submission_timeout, 5.0)

    def test_relaxed(self):
        policy = TimeoutPolicy.relaxed()
        self.assertGreater(policy.submission_timeout, 5.0)


if __name__ == '__main__':
    unittest.main()
