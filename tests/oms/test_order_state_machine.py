"""Tests for OrderStateMachine — strict state transition validation."""

import os
import sys
import types
import importlib.util
import unittest

# ── Bootstrap ──────────────────────────────────────
_ws = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
_oms_dir = os.path.join(_ws, 'services', 'oms')
_domain_dir = os.path.join(_oms_dir, 'domain')
_app_dir = os.path.join(_oms_dir, 'application')
_errors_dir = os.path.join(_oms_dir, 'errors')

if 'services' not in sys.modules:
    _svc = types.ModuleType('services')
    _svc.__path__ = [os.path.join(_ws, 'services')]
    sys.modules['services'] = _svc
if 'services.oms' not in sys.modules:
    _mod = types.ModuleType('services.oms')
    _mod.__path__ = [_oms_dir]
    sys.modules['services.oms'] = _mod
if 'services.oms.domain' not in sys.modules:
    _pkg = types.ModuleType('services.oms.domain')
    _pkg.__path__ = [_domain_dir]
    sys.modules['services.oms.domain'] = _pkg
if 'services.oms.application' not in sys.modules:
    _pkg_app = types.ModuleType('services.oms.application')
    _pkg_app.__path__ = [_app_dir]
    sys.modules['services.oms.application'] = _pkg_app
if 'services.oms.errors' not in sys.modules:
    _pkg2 = types.ModuleType('services.oms.errors')
    _pkg2.__path__ = [_errors_dir]
    sys.modules['services.oms.errors'] = _pkg2

_domain_files = [
    'order_id', 'order_status', 'order_side', 'order_type',
    'time_in_force', 'order_quantity', 'order_price',
    'order_lifecycle', 'order',
]
for _name in _domain_files:
    _fp = os.path.join(_domain_dir, f'{_name}.py')
    _mod_name = f'services.oms.domain.{_name}'
    if _mod_name not in sys.modules and os.path.exists(_fp):
        _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
        _m = importlib.util.module_from_spec(_spec)
        sys.modules[_mod_name] = _m
        _spec.loader.exec_module(_m)

_error_files = ['order_errors', 'lifecycle_errors']
for _name in _error_files:
    _fp = os.path.join(_errors_dir, f'{_name}.py')
    _mod_name = f'services.oms.errors.{_name}'
    if _mod_name not in sys.modules and os.path.exists(_fp):
        _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
        _m = importlib.util.module_from_spec(_spec)
        sys.modules[_mod_name] = _m
        _spec.loader.exec_module(_m)

_app_files = ['order_state_machine']
for _name in _app_files:
    _fp = os.path.join(_app_dir, f'{_name}.py')
    _mod_name = f'services.oms.application.{_name}'
    if _mod_name not in sys.modules and os.path.exists(_fp):
        _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
        _m = importlib.util.module_from_spec(_spec)
        sys.modules[_mod_name] = _m
        _spec.loader.exec_module(_m)

from services.oms.domain.order_status import OrderStatus
from services.oms.domain.order_lifecycle import LifecycleEventType
from services.oms.errors.lifecycle_errors import (
    InvalidStateTransitionError,
    TerminalStateModificationError,
)
from services.oms.application.order_state_machine import OrderStateMachine


class TestValidTransitions(unittest.TestCase):

    def test_received_to_accepted(self):
        self.assertTrue(OrderStateMachine.can_transition(
            OrderStatus.RECEIVED, LifecycleEventType.ORDER_ACCEPTED,
        ))

    def test_accepted_to_created(self):
        self.assertTrue(OrderStateMachine.can_transition(
            OrderStatus.ACCEPTED, LifecycleEventType.ORDER_CREATED,
        ))

    def test_created_to_routing(self):
        self.assertTrue(OrderStateMachine.can_transition(
            OrderStatus.CREATED, LifecycleEventType.ORDER_ROUTING_STARTED,
        ))

    def test_routing_to_working(self):
        self.assertTrue(OrderStateMachine.can_transition(
            OrderStatus.ROUTING, LifecycleEventType.ORDER_WORKING,
        ))

    def test_working_to_filled(self):
        self.assertTrue(OrderStateMachine.can_transition(
            OrderStatus.WORKING, LifecycleEventType.ORDER_FILLED,
        ))

    def test_working_to_partial_fill(self):
        self.assertTrue(OrderStateMachine.can_transition(
            OrderStatus.WORKING, LifecycleEventType.ORDER_PARTIAL_FILL,
        ))

    def test_partial_to_partial(self):
        self.assertTrue(OrderStateMachine.can_transition(
            OrderStatus.PARTIALLY_FILLED,
            LifecycleEventType.ORDER_PARTIAL_FILL,
        ))

    def test_partial_to_filled(self):
        self.assertTrue(OrderStateMachine.can_transition(
            OrderStatus.PARTIALLY_FILLED,
            LifecycleEventType.ORDER_FILLED,
        ))


class TestInvalidTransitions(unittest.TestCase):

    def test_received_to_filled_invalid(self):
        self.assertFalse(OrderStateMachine.can_transition(
            OrderStatus.RECEIVED, LifecycleEventType.ORDER_FILLED,
        ))

    def test_working_to_received_invalid(self):
        self.assertFalse(OrderStateMachine.can_transition(
            OrderStatus.WORKING, LifecycleEventType.ORDER_ACCEPTED,
        ))

    def test_skip_states_invalid(self):
        # Can't go from ACCEPTED directly to WORKING
        self.assertFalse(OrderStateMachine.can_transition(
            OrderStatus.ACCEPTED, LifecycleEventType.ORDER_WORKING,
        ))

    def test_transition_raises_on_invalid(self):
        with self.assertRaises(InvalidStateTransitionError):
            OrderStateMachine.transition(
                OrderStatus.RECEIVED, LifecycleEventType.ORDER_FILLED,
            )


class TestTerminalStateProtection(unittest.TestCase):

    def test_filled_cannot_transition(self):
        with self.assertRaises(TerminalStateModificationError):
            OrderStateMachine.transition(
                OrderStatus.FILLED, LifecycleEventType.ORDER_WORKING,
            )

    def test_cancelled_cannot_transition(self):
        with self.assertRaises(TerminalStateModificationError):
            OrderStateMachine.transition(
                OrderStatus.CANCELLED, LifecycleEventType.ORDER_WORKING,
            )

    def test_rejected_cannot_transition(self):
        with self.assertRaises(TerminalStateModificationError):
            OrderStateMachine.transition(
                OrderStatus.REJECTED, LifecycleEventType.ORDER_ACCEPTED,
            )

    def test_expired_cannot_transition(self):
        with self.assertRaises(TerminalStateModificationError):
            OrderStateMachine.transition(
                OrderStatus.EXPIRED, LifecycleEventType.ORDER_WORKING,
            )

    def test_is_terminal(self):
        self.assertTrue(OrderStateMachine.is_terminal(OrderStatus.FILLED))
        self.assertTrue(OrderStateMachine.is_terminal(OrderStatus.CANCELLED))
        self.assertFalse(OrderStateMachine.is_terminal(OrderStatus.WORKING))


class TestEventSequenceValidation(unittest.TestCase):

    def test_valid_sequence(self):
        seq = [
            LifecycleEventType.ORDER_RECEIVED,
            LifecycleEventType.ORDER_ACCEPTED,
            LifecycleEventType.ORDER_CREATED,
            LifecycleEventType.ORDER_ROUTING_STARTED,
            LifecycleEventType.ORDER_WORKING,
            LifecycleEventType.ORDER_FILLED,
        ]
        self.assertTrue(OrderStateMachine.is_valid_event_sequence(seq))

    def test_invalid_sequence_skip(self):
        seq = [
            LifecycleEventType.ORDER_RECEIVED,
            LifecycleEventType.ORDER_ACCEPTED,
            LifecycleEventType.ORDER_WORKING,  # skip CREATED, ROUTING
        ]
        self.assertFalse(OrderStateMachine.is_valid_event_sequence(seq))

    def test_invalid_sequence_wrong_start(self):
        seq = [LifecycleEventType.ORDER_ACCEPTED]
        self.assertFalse(OrderStateMachine.is_valid_event_sequence(seq))

    def test_empty_sequence_valid(self):
        self.assertTrue(OrderStateMachine.is_valid_event_sequence([]))


class TestAllowedEvents(unittest.TestCase):

    def test_working_allows_fill_and_cancel(self):
        events = OrderStateMachine.allowed_events(OrderStatus.WORKING)
        self.assertIn(LifecycleEventType.ORDER_FILLED, events)
        self.assertIn(LifecycleEventType.ORDER_PARTIAL_FILL, events)
        self.assertIn(LifecycleEventType.ORDER_CANCEL_REQUESTED, events)

    def test_terminal_no_events(self):
        self.assertEqual(
            OrderStateMachine.allowed_events(OrderStatus.FILLED), [],
        )


if __name__ == '__main__':
    unittest.main()
