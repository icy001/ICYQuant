"""Tests for DeliveryManager — retry, idempotency, conflict detection."""

import unittest

from services.oms.delivery.delivery_manager import DeliveryManager
from services.oms.delivery.delivery_policy import DeliveryPolicy
from services.oms.delivery.delivery_state import DeliveryState


class TestDeliveryManager(unittest.TestCase):

    def setUp(self):
        self.policy = DeliveryPolicy(max_attempts=3, initial_backoff_ms=1)
        self.manager = DeliveryManager(self.policy)

    def test_successful_delivery(self):
        result = self.manager.deliver(
            "REQ-001", lambda: "OK", request_hash="hash1",
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["attempts"], 1)

    def test_idempotent_replay(self):
        self.manager.deliver("REQ-001", lambda: "OK", request_hash="hash1")
        result = self.manager.deliver("REQ-001", lambda: "OK", request_hash="hash1")
        self.assertTrue(result["success"])
        self.assertTrue(result.get("idempotent"))

    def test_request_hash_conflict(self):
        self.manager.deliver("REQ-001", lambda: "OK", request_hash="hash1")
        result = self.manager.deliver("REQ-001", lambda: "OK", request_hash="hash2")
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "REQUEST_ID_REUSE_CONFLICT")

    def test_retry_on_failure(self):
        attempts = []

        def flaky_deliver():
            attempts.append(1)
            if len(attempts) < 3:
                raise ConnectionError("NETWORK_TIMEOUT")
            return "OK"

        # Need to make the error have a code attribute
        class RetryableError(Exception):
            code = "NETWORK_TIMEOUT"

        def flaky_deliver2():
            attempts.append(1)
            if len(attempts) < 3:
                raise RetryableError("timeout")
            return "OK"

        result = self.manager.deliver("REQ-001", flaky_deliver2)
        self.assertTrue(result["success"])
        self.assertEqual(len(attempts), 3)

    def test_non_retryable_error(self):
        class NonRetryableError(Exception):
            code = "INVALID_REQUEST"

        result = self.manager.deliver(
            "REQ-001", lambda: (_ for _ in ()).throw(NonRetryableError("bad")),
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "INVALID_REQUEST")
        self.assertEqual(result["attempts"], 1)


class TestDeliveryPolicy(unittest.TestCase):

    def test_is_retryable(self):
        policy = DeliveryPolicy.default()
        self.assertTrue(policy.is_retryable("NETWORK_TIMEOUT"))
        self.assertFalse(policy.is_retryable("INVALID_REQUEST"))

    def test_backoff_calculation(self):
        policy = DeliveryPolicy(
            initial_backoff_ms=100, max_backoff_ms=5000,
            backoff_multiplier=2.0,
        )
        self.assertEqual(policy.get_backoff_ms(1), 100)
        self.assertEqual(policy.get_backoff_ms(2), 200)
        self.assertEqual(policy.get_backoff_ms(3), 400)
        self.assertEqual(policy.get_backoff_ms(10), 5000)  # capped


if __name__ == '__main__':
    unittest.main()
