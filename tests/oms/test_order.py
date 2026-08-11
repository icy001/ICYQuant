"""Tests for OMS Order domain — Order, OrderId, OrderQuantity, etc."""

import os
import sys
import types
import importlib.util
import unittest

# ── Bootstrap: register packages manually ─────────────────────────
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
from services.oms.domain.order_id import OrderId
from services.oms.domain.order_status import OrderStatus
from services.oms.domain.order_side import OrderSide
from services.oms.domain.order_type import OrderType
from services.oms.domain.time_in_force import TimeInForce
from services.oms.domain.order_quantity import OrderQuantity, OrderQuantityError
from services.oms.domain.order_price import OrderPrice
from services.oms.domain.order_lifecycle import (
    OrderLifecycle, OrderLifecycleEvent, LifecycleEventType,
)


class TestOrderCreation(unittest.TestCase):
    """Order creation and initial state."""

    def test_create_basic_order(self):
        order = Order.create(
            symbol="NVDA",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000,
            lineage_id="LINEAGE-001",
            certificate_id="CERT-001",
            client_order_id="STRAT-007-000391",
        )
        self.assertEqual(order.symbol, "NVDA")
        self.assertEqual(order.side, OrderSide.BUY)
        self.assertEqual(order.quantity.original, 1000)
        self.assertEqual(order.quantity.filled, 0)
        self.assertEqual(order.quantity.remaining, 1000)
        self.assertEqual(order.status, OrderStatus.RECEIVED)
        self.assertEqual(order.lineage_id, "LINEAGE-001")
        self.assertEqual(order.certificate_id, "CERT-001")
        self.assertTrue(order.order_id.order_id.startswith("ORD-"))
        self.assertEqual(order.order_id.client_order_id, "STRAT-007-000391")

    def test_create_generates_initial_event(self):
        order = Order.create(
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=500,
            limit_price=195.50,
            lineage_id="L-1",
            certificate_id="C-1",
        )
        self.assertEqual(len(order.lifecycle.events), 1)
        evt = order.lifecycle.events[0]
        self.assertEqual(evt.event_type, LifecycleEventType.ORDER_RECEIVED)
        self.assertEqual(evt.lineage_id, "L-1")
        self.assertEqual(evt.certificate_id, "C-1")

    def test_create_with_limit_price(self):
        order = Order.create(
            symbol="TSLA",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=200,
            limit_price=250.00,
            lineage_id="L-2",
            certificate_id="C-2",
        )
        self.assertEqual(order.price.limit_price, 250.00)
        self.assertTrue(order.price.has_limit)
        self.assertEqual(order.notional_value, 200 * 250.00)

    def test_create_with_parent(self):
        order = Order.create(
            symbol="SPY",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10000,
            lineage_id="L-3",
            certificate_id="C-3",
            client_order_id="CHILD-001",
            parent_order_id="PARENT-001",
            root_order_id="PARENT-001",
        )
        self.assertTrue(order.order_id.is_child)
        self.assertEqual(order.order_id.parent_order_id, "PARENT-001")
        self.assertEqual(order.order_id.root_order_id, "PARENT-001")


class TestOrderQuantity(unittest.TestCase):

    def test_quantity_initialization(self):
        qty = OrderQuantity.for_original(1000)
        self.assertEqual(qty.original, 1000)
        self.assertEqual(qty.filled, 0)
        self.assertEqual(qty.remaining, 1000)
        self.assertEqual(qty.cancelled, 0)

    def test_fill(self):
        qty = OrderQuantity.for_original(1000)
        qty.fill(300)
        self.assertEqual(qty.filled, 300)
        self.assertEqual(qty.remaining, 700)

    def test_multiple_fills(self):
        qty = OrderQuantity.for_original(1000)
        qty.fill(300)
        qty.fill(400)
        self.assertEqual(qty.filled, 700)
        self.assertEqual(qty.remaining, 300)

    def test_fill_exceeds_remaining(self):
        qty = OrderQuantity.for_original(1000)
        with self.assertRaises(ValueError):
            qty.fill(1001)

    def test_cancel_remaining(self):
        qty = OrderQuantity.for_original(1000)
        qty.fill(600)
        qty.cancel_remaining()
        self.assertEqual(qty.filled, 600)
        self.assertEqual(qty.cancelled, 400)
        self.assertEqual(qty.remaining, 0)

    def test_quantity_invariant_maintained(self):
        qty = OrderQuantity.for_original(1000)
        qty.fill(300)
        qty.fill(200)
        qty.cancel_remaining()
        total = qty.filled + qty.remaining + qty.cancelled
        self.assertEqual(total, qty.original)

    def test_fill_pct(self):
        qty = OrderQuantity.for_original(1000)
        qty.fill(250)
        self.assertAlmostEqual(qty.fill_pct, 25.0)


class TestOrderId(unittest.TestCase):

    def test_order_id_generation(self):
        oid = OrderId()
        self.assertTrue(oid.order_id.startswith("ORD-"))

    def test_order_id_with_client(self):
        oid = OrderId(client_order_id="CLIENT-001")
        self.assertEqual(oid.client_order_id, "CLIENT-001")

    def test_is_child(self):
        oid = OrderId(parent_order_id="PARENT-001")
        self.assertTrue(oid.is_child)

    def test_equality(self):
        a = OrderId(order_id="ORD-001")
        b = OrderId(order_id="ORD-001")
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))


class TestOrderStatus(unittest.TestCase):

    def test_terminal_states(self):
        self.assertTrue(OrderStatus.FILLED.is_terminal)
        self.assertTrue(OrderStatus.CANCELLED.is_terminal)
        self.assertTrue(OrderStatus.REJECTED.is_terminal)
        self.assertTrue(OrderStatus.EXPIRED.is_terminal)
        self.assertTrue(OrderStatus.FAILED.is_terminal)

    def test_non_terminal_states(self):
        self.assertFalse(OrderStatus.RECEIVED.is_terminal)
        self.assertFalse(OrderStatus.WORKING.is_terminal)
        self.assertFalse(OrderStatus.PARTIALLY_FILLED.is_terminal)

    def test_active_states(self):
        self.assertTrue(OrderStatus.RECEIVED.is_active)
        self.assertTrue(OrderStatus.WORKING.is_active)
        self.assertFalse(OrderStatus.FILLED.is_active)

    def test_cancellable_states(self):
        self.assertTrue(OrderStatus.WORKING.can_be_cancelled)
        self.assertTrue(OrderStatus.PARTIALLY_FILLED.can_be_cancelled)
        self.assertFalse(OrderStatus.FILLED.can_be_cancelled)
        self.assertFalse(OrderStatus.RECEIVED.can_be_cancelled)


class TestOrderSerialization(unittest.TestCase):

    def test_to_dict(self):
        order = Order.create(
            symbol="NVDA",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1000,
            limit_price=850.00,
            lineage_id="L-1",
            certificate_id="C-1",
            account_id="ACC-001",
        )
        d = order.to_dict()
        self.assertEqual(d["symbol"], "NVDA")
        self.assertEqual(d["side"], "BUY")
        self.assertEqual(d["original_quantity"], 1000)
        self.assertEqual(d["status"], "RECEIVED")
        self.assertEqual(d["lineage_id"], "L-1")
        self.assertEqual(d["certificate_id"], "C-1")
        self.assertEqual(d["account_id"], "ACC-001")
        self.assertEqual(len(d["lifecycle_events"]), 1)


if __name__ == '__main__':
    unittest.main()
