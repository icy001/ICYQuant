"""Tests for OrderService — full OMS application service."""

import os
import sys
import types
import importlib.util
import time
import unittest

# ── Bootstrap ──────────────────────────────────────
_ws = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
_oms_dir = os.path.join(_ws, 'services', 'oms')
_domain_dir = os.path.join(_oms_dir, 'domain')
_app_dir = os.path.join(_oms_dir, 'application')
_ports_dir = os.path.join(_oms_dir, 'ports')
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
if 'services.oms.ports' not in sys.modules:
    _pkg_ports = types.ModuleType('services.oms.ports')
    _pkg_ports.__path__ = [_ports_dir]
    sys.modules['services.oms.ports'] = _pkg_ports
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

_app_files = ['order_state_machine', 'order_acceptor',
              'order_lifecycle_manager', 'order_service']
for _name in _app_files:
    _fp = os.path.join(_app_dir, f'{_name}.py')
    _mod_name = f'services.oms.application.{_name}'
    if _mod_name not in sys.modules and os.path.exists(_fp):
        _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
        _m = importlib.util.module_from_spec(_spec)
        sys.modules[_mod_name] = _m
        _spec.loader.exec_module(_m)

_ports_files = ['order_repository', 'order_event_store', 'execution_gateway']
for _name in _ports_files:
    _fp = os.path.join(_ports_dir, f'{_name}.py')
    _mod_name = f'services.oms.ports.{_name}'
    if _mod_name not in sys.modules and os.path.exists(_fp):
        _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
        _m = importlib.util.module_from_spec(_spec)
        sys.modules[_mod_name] = _m
        _spec.loader.exec_module(_m)

from services.oms.domain.order_status import OrderStatus
from services.oms.domain.order_side import OrderSide
from services.oms.domain.order_type import OrderType
from services.oms.domain.time_in_force import TimeInForce
from services.oms.domain.order_lifecycle import LifecycleEventType
from services.oms.errors.order_errors import (
    OrderNotFoundError,
    OrderIdempotencyError,
    ParentQuantityExceededError,
    ConcurrentModificationError,
)
from services.oms.errors.lifecycle_errors import (
    InvalidStateTransitionError,
    TerminalStateModificationError,
)
from services.oms.application.order_acceptor import (
    OrderAcceptor, AdmissionRequest,
)
from services.oms.application.order_lifecycle_manager import (
    OrderLifecycleManager,
)
from services.oms.application.order_service import OrderService
from services.oms.ports.order_repository import InMemoryOrderRepository
from services.oms.ports.order_event_store import InMemoryOrderEventStore
from services.oms.ports.execution_gateway import (
    InMemoryExecutionGateway, ExecutionStatus,
)


def _make_request(**overrides) -> AdmissionRequest:
    defaults = dict(
        certificate_id="CERT-001",
        flow_id="FLOW-001",
        lineage_id="LINEAGE-001",
        decision_id="DEC-001",
        order_intent_id="INTENT-001",
        client_order_id="STRAT-007-000391",
        symbol="NVDA",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=1000,
    )
    defaults.update(overrides)
    return AdmissionRequest(**defaults)


def _new_service() -> OrderService:
    return OrderService(
        repository=InMemoryOrderRepository(),
        event_store=InMemoryOrderEventStore(),
        execution_gateway=InMemoryExecutionGateway(),
    )


class TestFullLifecycle(unittest.TestCase):

    def setUp(self):
        self.svc = _new_service()
        self.order = self.svc.accept_order(_make_request())

    def test_accept_order(self):
        self.assertEqual(self.order.status, OrderStatus.ACCEPTED)

    def test_create_order(self):
        order = self.svc.create_order(self.order.order_id.order_id)
        self.assertEqual(order.status, OrderStatus.CREATED)

    def test_full_happy_path(self):
        oid = self.order.order_id.order_id
        self.svc.create_order(oid)
        self.svc.route_order(oid)
        order = self.svc.submit_order(oid)
        self.assertEqual(order.status, OrderStatus.WORKING)

    def test_full_fill(self):
        oid = self.order.order_id.order_id
        self.svc.create_order(oid)
        self.svc.route_order(oid)
        self.svc.submit_order(oid)
        order = self.svc.apply_fill(oid, 1000, 850.0, "EXEC-001")
        self.assertEqual(order.status, OrderStatus.FILLED)
        self.assertEqual(order.quantity.filled, 1000)
        self.assertEqual(order.quantity.remaining, 0)

    def test_partial_fill_then_full(self):
        oid = self.order.order_id.order_id
        self.svc.create_order(oid)
        self.svc.route_order(oid)
        self.svc.submit_order(oid)
        order = self.svc.apply_fill(oid, 300, 850.0, "EXEC-001")
        self.assertEqual(order.status, OrderStatus.PARTIALLY_FILLED)
        order = self.svc.apply_fill(oid, 700, 851.0, "EXEC-002")
        self.assertEqual(order.status, OrderStatus.FILLED)


class TestCancelFlow(unittest.TestCase):

    def setUp(self):
        self.svc = _new_service()
        self.order = self.svc.accept_order(_make_request())
        oid = self.order.order_id.order_id
        self.svc.create_order(oid)
        self.svc.route_order(oid)
        self.svc.submit_order(oid)

    def test_cancel_request_then_confirm(self):
        oid = self.order.order_id.order_id
        order = self.svc.cancel_order(oid, reason="User cancel")
        self.assertEqual(order.status, OrderStatus.WORKING)  # still working
        order = self.svc.confirm_cancel(oid, reason="Confirmed")
        self.assertEqual(order.status, OrderStatus.CANCELLED)
        self.assertEqual(order.quantity.cancelled, 1000)


class TestReject(unittest.TestCase):

    def setUp(self):
        self.svc = _new_service()
        self.order = self.svc.accept_order(_make_request())

    def test_reject(self):
        oid = self.order.order_id.order_id
        self.svc.create_order(oid)
        order = self.svc.reject_order(oid, reason="Venue reject")
        self.assertEqual(order.status, OrderStatus.REJECTED)
        self.assertTrue(order.status.is_terminal)


class TestExpiration(unittest.TestCase):

    def test_expire_order(self):
        svc = _new_service()
        past_time = time.time() - 60
        order = svc.accept_order(_make_request(expires_at=past_time))
        oid = order.order_id.order_id
        svc.create_order(oid)
        svc.route_order(oid)
        svc.submit_order(oid)
        order = svc.expire_order(oid)
        self.assertEqual(order.status, OrderStatus.EXPIRED)


class TestIdempotency(unittest.TestCase):

    def test_duplicate_client_order_id(self):
        svc = _new_service()
        svc.accept_order(_make_request(client_order_id="DUP-001"))
        with self.assertRaises(OrderIdempotencyError):
            svc.accept_order(_make_request(client_order_id="DUP-001"))


class TestParentChildOrders(unittest.TestCase):

    def setUp(self):
        self.svc = _new_service()
        self.parent = self.svc.accept_order(_make_request(
            client_order_id="PARENT-001",
            quantity=10000,
        ))

    def test_create_child_order(self):
        req = _make_request(
            client_order_id="CHILD-001",
            quantity=3000,
        )
        child = self.svc.create_child_order(req, self.parent.order_id.order_id, 3000)
        self.assertEqual(child.quantity.original, 3000)
        self.assertEqual(child.order_id.parent_order_id, self.parent.order_id.order_id)

    def test_parent_quantity_exceeded(self):
        # First child: 6000
        req1 = _make_request(client_order_id="CHILD-001", quantity=6000)
        self.svc.create_child_order(req1, self.parent.order_id.order_id, 6000)
        # Second child: 5000 (exceeds remaining 4000)
        req2 = _make_request(client_order_id="CHILD-002", quantity=5000)
        with self.assertRaises(ParentQuantityExceededError):
            self.svc.create_child_order(req2, self.parent.order_id.order_id, 5000)


class TestVersionConflict(unittest.TestCase):

    def test_concurrent_modification(self):
        svc = _new_service()
        order = svc.accept_order(_make_request())
        oid = order.order_id.order_id
        # Wrong expected_version
        with self.assertRaises(ConcurrentModificationError):
            svc.create_order(oid, expected_version=999)


class TestQuantityInvariants(unittest.TestCase):

    def test_fill_exceeds_quantity(self):
        svc = _new_service()
        order = svc.accept_order(_make_request(quantity=1000))
        oid = order.order_id.order_id
        svc.create_order(oid)
        svc.route_order(oid)
        svc.submit_order(oid)
        with self.assertRaises(Exception):
            svc.apply_fill(oid, 1001, 850.0, "EXEC-001")


class TestUnknownExecutionState(unittest.TestCase):

    def test_timeout_does_not_fail(self):
        repo = InMemoryOrderRepository()
        gateway = InMemoryExecutionGateway()
        gateway.configure_timeout(True)
        svc = OrderService(repository=repo, execution_gateway=gateway)
        order = svc.accept_order(_make_request())
        oid = order.order_id.order_id
        svc.create_order(oid)
        svc.route_order(oid)
        result = svc.submit_order(oid)
        # Should be marked unknown, NOT failed
        self.assertTrue(result.execution_status_unknown)
        self.assertNotEqual(result.status, OrderStatus.FAILED)


class TestLifecycleAudit(unittest.TestCase):

    def test_events_stored(self):
        repo = InMemoryOrderRepository()
        event_store = InMemoryOrderEventStore()
        svc = OrderService(repository=repo, event_store=event_store)
        order = svc.accept_order(_make_request())
        oid = order.order_id.order_id
        svc.create_order(oid)
        svc.route_order(oid)
        svc.submit_order(oid)
        # Should have: RECEIVED + ACCEPTED + CREATED + ROUTING + WORKING
        self.assertGreaterEqual(event_store.count, 5)

    def test_get_lifecycle_events(self):
        svc = _new_service()
        order = svc.accept_order(_make_request())
        events = svc.get_lifecycle_events(order.order_id.order_id)
        self.assertGreaterEqual(len(events), 2)


class TestLineagePropagation(unittest.TestCase):

    def test_lineage_in_events(self):
        svc = _new_service()
        order = svc.accept_order(_make_request(lineage_id="LINEAGE-E2E"))
        oid = order.order_id.order_id
        svc.create_order(oid)
        svc.route_order(oid)
        events = svc.get_lifecycle_events(oid)
        for evt in events:
            self.assertEqual(evt.lineage_id, "LINEAGE-E2E")
            self.assertEqual(evt.certificate_id, "CERT-001")


class TestQueries(unittest.TestCase):

    def test_get_order_not_found(self):
        svc = _new_service()
        with self.assertRaises(OrderNotFoundError):
            svc.get_order("NONEXISTENT")

    def test_get_active_orders(self):
        svc = _new_service()
        svc.accept_order(_make_request(client_order_id="A-1"))
        svc.accept_order(_make_request(client_order_id="A-2"))
        active = svc.get_active_orders()
        self.assertEqual(len(active), 2)


if __name__ == '__main__':
    unittest.main()
