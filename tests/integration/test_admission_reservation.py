"""Tests for AdmissionReservation: balance tracking, reserve, release, convert."""

from __future__ import annotations

import sys
import os
import types
import importlib.util
import unittest

_ws = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if "services" not in sys.modules:
    _svc = types.ModuleType("services"); _svc.__path__ = [os.path.join(_ws, "services")]
    sys.modules["services"] = _svc
_int_dir = os.path.join(_ws, "services", "integration")
if "services.integration" not in sys.modules:
    _mod = types.ModuleType("services.integration"); _mod.__path__ = [_int_dir]
    sys.modules["services.integration"] = _mod
for _name in [
    "order_intent","order_constraints","order_fingerprint","order_certificate",
    "admission_state","admission_context","admission_request","admission_result",
    "admission_decision","admission_policy","admission_validator","admission_authorizer",
    "admission_normalizer","admission_deduplicator","admission_reservation",
    "admission_gate","admission_registry","admission_metrics","order_admission",
]:
    _fp = os.path.join(_int_dir, f"{_name}.py")
    if not os.path.exists(_fp): continue
    _mod_name = f"services.integration.{_name}"
    if _mod_name in sys.modules: continue
    _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
    _m = importlib.util.module_from_spec(_spec)
    sys.modules[_mod_name] = _m
    _spec.loader.exec_module(_m)

from services.integration.order_intent import OrderIntent, Side, OrderType
from services.integration.admission_reservation import (
    AdmissionReservation, ReservationStatus,
)


class TestAdmissionReservation(unittest.TestCase):

    def setUp(self):
        self.resv = AdmissionReservation()
        self.resv.set_balance("ACC-001", 1000000.0)
        self.intent = (OrderIntent()
                       .with_flow_id("FLOW-001")
                       .with_account_id("ACC-001")
                       .with_symbol("NVDA")
                       .with_side(Side.BUY)
                       .with_quantity(1000)
                       .with_limit_price(180.0)
                       .with_order_type(OrderType.LIMIT))

    def test_successful_reservation(self):
        result = self.resv.reserve(self.intent, "ORDER-001")
        self.assertTrue(result.success)
        self.assertEqual(result.code, "RESERVATION_SUCCESS")
        self.assertIsNotNone(result.reservation)
        self.assertEqual(result.reservation.amount_reserved, 180000.0)

    def test_reservation_deducts_balance(self):
        self.resv.reserve(self.intent, "ORDER-001")
        available = self.resv.get_available("ACC-001")
        self.assertEqual(available, 1000000.0 - 180000.0)

    def test_insufficient_balance(self):
        self.resv.set_balance("ACC-001", 100000.0)
        result = self.resv.reserve(self.intent, "ORDER-001")
        self.assertFalse(result.success)
        self.assertEqual(result.code, "INSUFFICIENT_BALANCE")

    def test_zero_notional_fails(self):
        intent = (OrderIntent()
                  .with_account_id("ACC-001")
                  .with_quantity(0)
                  .with_limit_price(180.0))
        result = self.resv.reserve(intent, "ORDER-001")
        self.assertFalse(result.success)
        self.assertEqual(result.code, "INVALID_NOTIONAL")

    def test_release_returns_balance(self):
        result = self.resv.reserve(self.intent, "ORDER-001")
        rid = result.reservation.reservation_id
        released = self.resv.release(rid)
        self.assertIsNotNone(released)
        self.assertEqual(released.status, ReservationStatus.RELEASED)
        self.assertEqual(self.resv.get_available("ACC-001"), 1000000.0)

    def test_release_idempotent(self):
        result = self.resv.reserve(self.intent, "ORDER-001")
        rid = result.reservation.reservation_id
        self.resv.release(rid)
        self.resv.release(rid)  # second release should not double-add
        self.assertLessEqual(self.resv.get_available("ACC-001"), 1000000.0)

    def test_convert_tracks_execution(self):
        result = self.resv.reserve(self.intent, "ORDER-001")
        rid = result.reservation.reservation_id
        converted = self.resv.convert(rid)
        self.assertIsNotNone(converted)
        self.assertEqual(converted.status, ReservationStatus.CONVERTED)

    def test_get_nonexistent_reservation(self):
        self.assertIsNone(self.resv.get_reservation("BOGUS-ID"))

    def test_multiple_reservations(self):
        self.resv.reserve(self.intent, "ORDER-001")
        intent2 = (OrderIntent()
                   .with_flow_id("FLOW-002")
                   .with_account_id("ACC-001")
                   .with_symbol("AAPL")
                   .with_side(Side.BUY)
                   .with_quantity(500)
                   .with_limit_price(200.0)
                   .with_order_type(OrderType.LIMIT))
        result2 = self.resv.reserve(intent2, "ORDER-002")
        self.assertTrue(result2.success)
        # 1M - 180K - 100K = 720K
        self.assertEqual(self.resv.get_available("ACC-001"), 720000.0)


if __name__ == "__main__":
    unittest.main()
