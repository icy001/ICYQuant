"""Tests for OrderAcceptor — admission certificate → OMS order."""

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

_app_files = ['order_state_machine', 'order_acceptor', 'order_lifecycle_manager', 'order_service']
for _name in _app_files:
    _fp = os.path.join(_app_dir, f'{_name}.py')
    _mod_name = f'services.oms.application.{_name}'
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
    OrderNotAcceptedError,
    OrderCertificateError,
    OrderIdempotencyError,
)
from services.oms.application.order_acceptor import (
    OrderAcceptor, AdmissionRequest, CertificateVerification,
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


class TestAcceptHappyPath(unittest.TestCase):

    def setUp(self):
        self.acceptor = OrderAcceptor()

    def test_accept_creates_order(self):
        req = _make_request()
        order = self.acceptor.accept(req)
        self.assertEqual(order.symbol, "NVDA")
        self.assertEqual(order.certificate_id, "CERT-001")
        self.assertEqual(order.lineage_id, "LINEAGE-001")
        self.assertEqual(order.decision_id, "DEC-001")
        self.assertEqual(order.order_intent_id, "INTENT-001")
        self.assertEqual(order.flow_id, "FLOW-001")

    def test_accepted_status(self):
        order = self.acceptor.accept(_make_request())
        self.assertEqual(order.status, OrderStatus.ACCEPTED)

    def test_accepted_emits_event(self):
        order = self.acceptor.accept(_make_request())
        # ORDER_RECEIVED + ORDER_ACCEPTED
        self.assertEqual(len(order.lifecycle.events), 2)
        last = order.lifecycle.last_event()
        self.assertEqual(last.event_type, LifecycleEventType.ORDER_ACCEPTED)

    def test_accept_with_limit_order(self):
        req = _make_request(
            order_type=OrderType.LIMIT,
            limit_price=850.00,
        )
        order = self.acceptor.accept(req)
        self.assertEqual(order.price.limit_price, 850.00)


class TestCertificateVerification(unittest.TestCase):

    def test_invalid_certificate_rejected(self):
        def fail_verifier(cert_id):
            return CertificateVerification.fail("Expired")
        acceptor = OrderAcceptor(certificate_verifier=fail_verifier)
        with self.assertRaises(OrderCertificateError):
            acceptor.accept(_make_request())

    def test_empty_certificate_rejected(self):
        req = _make_request(certificate_id="")
        acceptor = OrderAcceptor()
        # Empty certificate fails at verification stage
        with self.assertRaises((OrderNotAcceptedError, OrderCertificateError)):
            acceptor.accept(req)


class TestIdempotency(unittest.TestCase):

    def test_duplicate_client_order_id(self):
        existing_orders = {}

        def idempotency_check(client_id):
            return existing_orders.get(client_id)

        acceptor = OrderAcceptor(idempotency_check=idempotency_check)

        # First accept
        order1 = acceptor.accept(_make_request(client_order_id="DUP-001"))
        existing_orders["DUP-001"] = order1

        # Second accept — should raise
        with self.assertRaises(OrderIdempotencyError):
            acceptor.accept(_make_request(client_order_id="DUP-001"))


class TestScopeValidation(unittest.TestCase):

    def test_scope_violation_rejected(self):
        def fail_scope(req, scope):
            return False
        acceptor = OrderAcceptor(scope_validator=fail_scope)
        with self.assertRaises(OrderNotAcceptedError):
            acceptor.accept(_make_request())


class TestConstraintValidation(unittest.TestCase):

    def test_zero_quantity_rejected(self):
        acceptor = OrderAcceptor()
        with self.assertRaises(OrderNotAcceptedError):
            acceptor.accept(_make_request(quantity=0))

    def test_negative_quantity_rejected(self):
        acceptor = OrderAcceptor()
        with self.assertRaises(OrderNotAcceptedError):
            acceptor.accept(_make_request(quantity=-100))

    def test_limit_order_without_price_rejected(self):
        acceptor = OrderAcceptor()
        req = _make_request(
            order_type=OrderType.LIMIT,
            limit_price=0,
        )
        with self.assertRaises(OrderNotAcceptedError):
            acceptor.accept(req)

    def test_missing_lineage_rejected(self):
        acceptor = OrderAcceptor()
        with self.assertRaises(OrderNotAcceptedError):
            acceptor.accept(_make_request(lineage_id=""))


class TestLineagePropagation(unittest.TestCase):

    def test_lineage_fields_propagated(self):
        acceptor = OrderAcceptor()
        order = acceptor.accept(_make_request(
            flow_id="FLOW-X",
            lineage_id="LINEAGE-X",
            decision_id="DEC-X",
            order_intent_id="INTENT-X",
            certificate_id="CERT-X",
        ))
        self.assertEqual(order.flow_id, "FLOW-X")
        self.assertEqual(order.lineage_id, "LINEAGE-X")
        self.assertEqual(order.decision_id, "DEC-X")
        self.assertEqual(order.order_intent_id, "INTENT-X")
        self.assertEqual(order.certificate_id, "CERT-X")

    def test_events_carry_lineage(self):
        acceptor = OrderAcceptor()
        order = acceptor.accept(_make_request(lineage_id="LINEAGE-L"))
        for evt in order.lifecycle.events:
            self.assertEqual(evt.lineage_id, "LINEAGE-L")


if __name__ == '__main__':
    unittest.main()
