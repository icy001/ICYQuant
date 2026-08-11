"""Tests for lifecycle validation — state transitions."""

import unittest

from services.oms.domain.order_status import OrderStatus
from services.oms.validation.lifecycle_validator import LifecycleValidator
from services.oms.results.command_errors import (
    InvalidStateTransitionError,
    TerminalStateError,
)


class TestLifecycleValidation(unittest.TestCase):

    def test_start_routing_from_created(self):
        LifecycleValidator.validate_transition(
            "START_ROUTING", OrderStatus.CREATED,
        )

    def test_start_routing_from_working_fails(self):
        with self.assertRaises(InvalidStateTransitionError):
            LifecycleValidator.validate_transition(
                "START_ROUTING", OrderStatus.WORKING,
            )

    def test_mark_working_from_routing(self):
        LifecycleValidator.validate_transition(
            "MARK_WORKING", OrderStatus.ROUTING,
        )

    def test_terminal_state_rejects_all(self):
        with self.assertRaises(TerminalStateError):
            LifecycleValidator.validate_transition(
                "START_ROUTING", OrderStatus.FILLED,
            )

    def test_can_apply_execution(self):
        self.assertTrue(LifecycleValidator.can_apply_execution(OrderStatus.WORKING))
        self.assertTrue(LifecycleValidator.can_apply_execution(OrderStatus.PARTIALLY_FILLED))
        self.assertFalse(LifecycleValidator.can_apply_execution(OrderStatus.FILLED))

    def test_can_cancel(self):
        self.assertTrue(LifecycleValidator.can_cancel(OrderStatus.WORKING))
        self.assertFalse(LifecycleValidator.can_cancel(OrderStatus.FILLED))

    def test_can_reject(self):
        self.assertTrue(LifecycleValidator.can_reject(OrderStatus.WORKING))
        self.assertFalse(LifecycleValidator.can_reject(OrderStatus.FILLED))

    def test_can_expire(self):
        self.assertTrue(LifecycleValidator.can_expire(OrderStatus.WORKING))
        self.assertFalse(LifecycleValidator.can_expire(OrderStatus.FILLED))


if __name__ == '__main__':
    unittest.main()
