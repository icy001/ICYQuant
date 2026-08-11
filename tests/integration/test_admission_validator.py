"""Tests for AdmissionValidator: structural and business validation."""

from __future__ import annotations

import sys
import os
import types
import importlib.util
import unittest

# ── Virtual package bootstrap ──────────────────────────────────
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
from services.integration.admission_request import AdmissionRequest
from services.integration.admission_validator import AdmissionValidator


class TestAdmissionValidator(unittest.TestCase):
    """Test admission validation."""

    def setUp(self):
        self.validator = AdmissionValidator()

    def _make_intent(self, **overrides):
        params = {
            "flow_id": "FLOW-001", "decision_id": "DEC-001",
            "strategy_id": "STRAT-001", "account_id": "ACC-001",
            "symbol": "NVDA", "side": Side.BUY, "quantity": 1000.0,
            "order_type": OrderType.LIMIT, "limit_price": 180.0,
        }
        params.update(overrides)
        intent = OrderIntent()
        for k, v in params.items():
            setattr(intent, k, v)
        return intent

    def test_valid_request_passes(self):
        intent = self._make_intent()
        req = AdmissionRequest(intent=intent)
        report = self.validator.validate(req)
        self.assertTrue(report.valid)
        self.assertEqual(len(report.errors), 0)

    def test_missing_intent(self):
        req = AdmissionRequest(intent=None)
        report = self.validator.validate(req)
        self.assertFalse(report.valid)
        self.assertTrue(any("intent" in e.field for e in report.errors))

    def test_missing_flow_id(self):
        intent = self._make_intent(flow_id="")
        req = AdmissionRequest(intent=intent)
        report = self.validator.validate(req)
        self.assertFalse(report.valid)
        self.assertTrue(any(e.code == "MISSING_FLOW_ID" for e in report.errors))

    def test_missing_symbol(self):
        intent = self._make_intent(symbol="")
        req = AdmissionRequest(intent=intent)
        report = self.validator.validate(req)
        self.assertFalse(report.valid)
        self.assertTrue(any(e.code == "MISSING_SYMBOL" for e in report.errors))

    def test_invalid_quantity(self):
        intent = self._make_intent(quantity=0)
        req = AdmissionRequest(intent=intent)
        report = self.validator.validate(req)
        self.assertFalse(report.valid)
        self.assertTrue(any("quantity" in e.field for e in report.errors))

    def test_negative_quantity(self):
        intent = self._make_intent(quantity=-100)
        req = AdmissionRequest(intent=intent)
        report = self.validator.validate(req)
        self.assertFalse(report.valid)

    def test_limit_order_missing_price(self):
        intent = self._make_intent(order_type=OrderType.LIMIT, limit_price=None)
        req = AdmissionRequest(intent=intent)
        report = self.validator.validate(req)
        self.assertFalse(report.valid)
        self.assertTrue(any(e.code == "MISSING_LIMIT_PRICE" for e in report.errors))

    def test_limit_order_zero_price(self):
        intent = self._make_intent(order_type=OrderType.LIMIT, limit_price=0)
        req = AdmissionRequest(intent=intent)
        report = self.validator.validate(req)
        self.assertFalse(report.valid)

    def test_market_order_no_limit_price_ok(self):
        intent = self._make_intent(order_type=OrderType.MARKET, limit_price=None)
        req = AdmissionRequest(intent=intent)
        report = self.validator.validate(req)
        self.assertTrue(report.valid)

    def test_missing_account_id(self):
        intent = self._make_intent(account_id="")
        req = AdmissionRequest(intent=intent)
        report = self.validator.validate(req)
        self.assertFalse(report.valid)

    def test_report_to_dict(self):
        intent = self._make_intent(symbol="")
        req = AdmissionRequest(intent=intent)
        report = self.validator.validate(req)
        d = report.to_dict()
        self.assertFalse(d["valid"])
        self.assertGreater(len(d["errors"]), 0)


if __name__ == "__main__":
    unittest.main()
