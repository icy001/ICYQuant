"""Tests for OrderLifecycle — event-driven state transitions."""

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

from services.oms.domain.order import Order
from services.oms.domain.order_side import OrderSide
from services.oms.domain.order_type import OrderType
from services.oms.domain.order_status import OrderStatus
from services.oms.domain.order_lifecycle import (
    OrderLifecycle, OrderLifecycleEvent, LifecycleEventType,
    LifecycleTransitionError,
)


class TestLifecycleEventSequence(unittest.TestCase):

    def setUp(self):
        self.order = Order.create(
            symbol="NVDA", side=OrderSide.BUY, order_type=OrderType.MARKET,
            quantity=1000, lineage_id="L-1", certificate_id="C-1",
        )

    def test_initial_received_event(self):
        self.assertEqual(len(self.order.lifecycle.events), 1)
        self.assertEqual(
            self.order.lifecycle.events[0].event_type,
            LifecycleEventType.ORDER_RECEIVED,
        )

    def test_full_happy_path_sequence(self):
        order = self.order
        # RECEIVED → ACCEPTED → CREATED → ROUTING → WORKING → FILLED
        for evt_type in [
            LifecycleEventType.ORDER_ACCEPTED,
            LifecycleEventType.ORDER_CREATED,
            LifecycleEventType.ORDER_ROUTING_STARTED,
            LifecycleEventType.ORDER_WORKING,
            LifecycleEventType.ORDER_FILLED,
        ]:
            event = OrderLifecycleEvent.create(
                event_type=evt_type,
                order_id=order.order_id.order_id,
                previous_status=order.status,
                lineage_id=order.lineage_id,
                certificate_id=order.certificate_id,
            )
            order.apply_event(event)

        self.assertEqual(order.status, OrderStatus.FILLED)
        self.assertEqual(len(order.lifecycle.events), 6)

    def test_partial_fill_sequence(self):
        order = self.order
        events = [
            LifecycleEventType.ORDER_ACCEPTED,
            LifecycleEventType.ORDER_CREATED,
            LifecycleEventType.ORDER_ROUTING_STARTED,
            LifecycleEventType.ORDER_WORKING,
            LifecycleEventType.ORDER_PARTIAL_FILL,
            LifecycleEventType.ORDER_PARTIAL_FILL,
            LifecycleEventType.ORDER_FILLED,
        ]
        for evt_type in events:
            event = OrderLifecycleEvent.create(
                event_type=evt_type,
                order_id=order.order_id.order_id,
                previous_status=order.status,
                lineage_id=order.lineage_id,
                certificate_id=order.certificate_id,
            )
            order.apply_event(event)

        self.assertEqual(order.status, OrderStatus.FILLED)
        self.assertEqual(len(order.lifecycle.events), 8)


class TestLifecycleTerminalProtection(unittest.TestCase):

    def setUp(self):
        self.order = Order.create(
            symbol="AAPL", side=OrderSide.SELL, order_type=OrderType.MARKET,
            quantity=500, lineage_id="L-2", certificate_id="C-2",
        )

    def _advance_to(self, status: OrderStatus):
        order = self.order
        transitions = [
            LifecycleEventType.ORDER_ACCEPTED,
            LifecycleEventType.ORDER_CREATED,
            LifecycleEventType.ORDER_ROUTING_STARTED,
            LifecycleEventType.ORDER_WORKING,
        ]
        if status == OrderStatus.FILLED:
            transitions.append(LifecycleEventType.ORDER_FILLED)
        elif status == OrderStatus.CANCELLED:
            transitions.append(LifecycleEventType.ORDER_CANCELLED)
        for evt_type in transitions:
            event = OrderLifecycleEvent.create(
                event_type=evt_type,
                order_id=order.order_id.order_id,
                previous_status=order.status,
                lineage_id=order.lineage_id,
                certificate_id=order.certificate_id,
            )
            order.apply_event(event)

    def test_filled_is_terminal(self):
        self._advance_to(OrderStatus.FILLED)
        self.assertTrue(self.order.status.is_terminal)

    def test_cancelled_is_terminal(self):
        self._advance_to(OrderStatus.CANCELLED)
        self.assertTrue(self.order.status.is_terminal)

    def test_cannot_transition_from_filled(self):
        self._advance_to(OrderStatus.FILLED)
        event = OrderLifecycleEvent.create(
            event_type=LifecycleEventType.ORDER_WORKING,
            order_id=self.order.order_id.order_id,
            previous_status=self.order.status,
            lineage_id=self.order.lineage_id,
            certificate_id=self.order.certificate_id,
        )
        with self.assertRaises(LifecycleTransitionError):
            self.order.apply_event(event)


class TestLifecycleConsistency(unittest.TestCase):

    def test_lifecycle_is_consistent_after_transitions(self):
        order = Order.create(
            symbol="TSLA", side=OrderSide.BUY, order_type=OrderType.MARKET,
            quantity=100, lineage_id="L-3", certificate_id="C-3",
        )
        for evt_type in [
            LifecycleEventType.ORDER_ACCEPTED,
            LifecycleEventType.ORDER_CREATED,
            LifecycleEventType.ORDER_ROUTING_STARTED,
            LifecycleEventType.ORDER_WORKING,
        ]:
            event = OrderLifecycleEvent.create(
                event_type=evt_type,
                order_id=order.order_id.order_id,
                previous_status=order.status,
                lineage_id=order.lineage_id,
                certificate_id=order.certificate_id,
            )
            order.apply_event(event)

        self.assertTrue(order.lifecycle.is_consistent())

    def test_event_carries_lineage(self):
        order = Order.create(
            symbol="SPY", side=OrderSide.BUY, order_type=OrderType.MARKET,
            quantity=1000, lineage_id="LINEAGE-E2E", certificate_id="CERT-X",
        )
        for evt in order.lifecycle.events:
            self.assertEqual(evt.lineage_id, "LINEAGE-E2E")
            self.assertEqual(evt.certificate_id, "CERT-X")


class TestLifecycleAuditFields(unittest.TestCase):

    def test_event_contains_audit_fields(self):
        order = Order.create(
            symbol="NVDA", side=OrderSide.BUY, order_type=OrderType.MARKET,
            quantity=100, lineage_id="L-AUDIT", certificate_id="C-AUDIT",
        )
        event = OrderLifecycleEvent.create(
            event_type=LifecycleEventType.ORDER_ACCEPTED,
            order_id=order.order_id.order_id,
            previous_status=order.status,
            lineage_id=order.lineage_id,
            certificate_id=order.certificate_id,
            actor="risk-service-v3",
            actor_type="RISK_ENGINE",
            reason="Certificate verified",
        )
        order.apply_event(event)

        last = order.lifecycle.last_event()
        self.assertEqual(last.actor, "risk-service-v3")
        self.assertEqual(last.actor_type, "RISK_ENGINE")
        self.assertEqual(last.reason, "Certificate verified")
        self.assertEqual(last.lineage_id, "L-AUDIT")
        self.assertEqual(last.certificate_id, "C-AUDIT")
        self.assertTrue(last.event_id.startswith("OL-EVT-"))
        self.assertTrue(last.timestamp > 0)


if __name__ == '__main__':
    unittest.main()
