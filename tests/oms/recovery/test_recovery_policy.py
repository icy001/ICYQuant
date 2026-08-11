"""Tests for RecoveryPolicy."""

import unittest

from services.oms.recovery.recovery_policy import RecoveryPolicy


class TestRecoveryPolicy(unittest.TestCase):

    def test_default(self):
        policy = RecoveryPolicy.default()
        self.assertTrue(policy.auto_recovery_enabled)
        self.assertEqual(policy.max_attempts, 3)

    def test_aggressive(self):
        policy = RecoveryPolicy.aggressive()
        self.assertEqual(policy.max_attempts, 5)
        self.assertLess(policy.query_timeout, 5.0)

    def test_conservative(self):
        policy = RecoveryPolicy.conservative()
        self.assertEqual(policy.max_attempts, 2)
        self.assertGreater(policy.query_timeout, 5.0)


if __name__ == '__main__':
    unittest.main()
