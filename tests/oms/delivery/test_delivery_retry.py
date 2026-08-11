"""Tests for delivery retry behavior."""

import unittest

from services.oms.delivery.delivery_manager import DeliveryManager
from services.oms.delivery.delivery_policy import DeliveryPolicy
from services.oms.delivery.delivery_state import DeliveryState


class TestDeliveryRetry(unittest.TestCase):

    def setUp(self):
        self.policy = DeliveryPolicy(
            max_attempts=3, initial_backoff_ms=1, max_backoff_ms=10,
        )
        self.manager = DeliveryManager(self.policy)

    def test_max_retries_exceeded(self):
        class TimeoutError(Exception):
            code = "NETWORK_TIMEOUT"

        def always_fail():
            raise TimeoutError("timeout")

        result = self.manager.deliver("REQ-001", always_fail)
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 3)

    def test_state_after_max_retries(self):
        class TimeoutError(Exception):
            code = "NETWORK_TIMEOUT"

        def always_fail():
            raise TimeoutError("timeout")

        self.manager.deliver("REQ-001", always_fail)
        state = self.manager.get_state("REQ-001")
        self.assertEqual(state, DeliveryState.UNKNOWN)

    def test_state_after_success(self):
        self.manager.deliver("REQ-001", lambda: "OK")
        state = self.manager.get_state("REQ-001")
        self.assertEqual(state, DeliveryState.ACKNOWLEDGED)

    def test_attempts_recorded(self):
        class TimeoutError(Exception):
            code = "NETWORK_TIMEOUT"

        call_count = []

        def fail_twice():
            call_count.append(1)
            if len(call_count) < 3:
                raise TimeoutError("timeout")
            return "OK"

        self.manager.deliver("REQ-001", fail_twice)
        attempts = self.manager.get_attempts("REQ-001")
        self.assertEqual(len(attempts), 3)
        self.assertFalse(attempts[0].success)
        self.assertTrue(attempts[2].success)


if __name__ == '__main__':
    unittest.main()
