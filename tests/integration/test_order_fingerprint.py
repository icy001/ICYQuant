"""Tests for OrderFingerprint: computation, deduplication, idempotency."""

from __future__ import annotations

import sys
import os
import types
import importlib.util
import unittest

# ── Virtual package bootstrap ──────────────────────────────────
_ws = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if "services" not in sys.modules:
    _svc = types.ModuleType("services")
    _svc.__path__ = [os.path.join(_ws, "services")]
    sys.modules["services"] = _svc

_int_dir = os.path.join(_ws, "services", "integration")

if "services.integration" not in sys.modules:
    _mod = types.ModuleType("services.integration")
    _mod.__path__ = [_int_dir]
    sys.modules["services.integration"] = _mod

for _name in [
    "order_intent", "order_constraints", "order_fingerprint",
    "order_certificate", "admission_state", "admission_context",
    "admission_request", "admission_result", "admission_decision",
    "admission_policy", "admission_validator", "admission_authorizer",
    "admission_normalizer", "admission_deduplicator",
    "admission_reservation", "admission_gate", "admission_registry",
    "admission_metrics", "order_admission",
]:
    _fp = os.path.join(_int_dir, f"{_name}.py")
    if not os.path.exists(_fp):
        continue
    _mod_name = f"services.integration.{_name}"
    if _mod_name in sys.modules:
        continue
    _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
    _m = importlib.util.module_from_spec(_spec)
    sys.modules[_mod_name] = _m
    _spec.loader.exec_module(_m)

from services.integration.order_intent import OrderIntent, Side, OrderType
from services.integration.order_fingerprint import OrderFingerprint


class TestOrderFingerprint(unittest.TestCase):
    """Test fingerprint computation and deduplication."""

    def test_compute_fingerprint(self):
        intent = (OrderIntent()
                  .with_flow_id("FLOW-001")
                  .with_account_id("ACC-001")
                  .with_strategy_id("STRAT-001")
                  .with_symbol("NVDA")
                  .with_side(Side.BUY)
                  .with_quantity(1000.0)
                  .with_order_type(OrderType.LIMIT)
                  .with_limit_price(180.0)
                  .with_venue("NASDAQ"))
        fp = OrderFingerprint.compute(intent)
        self.assertEqual(fp.intent_id, intent.intent_id)
        self.assertTrue(len(fp.fingerprint) == 64)  # SHA-256 hex
        self.assertFalse(fp.is_duplicate())

    def test_same_intent_same_fingerprint(self):
        intent1 = (OrderIntent()
                   .with_flow_id("FLOW-001")
                   .with_account_id("ACC-001")
                   .with_symbol("NVDA")
                   .with_side(Side.BUY)
                   .with_quantity(1000))
        intent2 = (OrderIntent()
                   .with_flow_id("FLOW-001")
                   .with_account_id("ACC-001")
                   .with_symbol("NVDA")
                   .with_side(Side.BUY)
                   .with_quantity(1000))
        fp1 = OrderFingerprint.compute(intent1)
        fp2 = OrderFingerprint.compute(intent2)
        self.assertEqual(fp1.fingerprint, fp2.fingerprint)

    def test_different_intent_different_fingerprint(self):
        intent1 = (OrderIntent()
                   .with_flow_id("FLOW-001")
                   .with_symbol("NVDA")
                   .with_side(Side.BUY)
                   .with_quantity(1000))
        intent2 = (OrderIntent()
                   .with_flow_id("FLOW-001")
                   .with_symbol("NVDA")
                   .with_side(Side.BUY)
                   .with_quantity(2000))
        fp1 = OrderFingerprint.compute(intent1)
        fp2 = OrderFingerprint.compute(intent2)
        self.assertNotEqual(fp1.fingerprint, fp2.fingerprint)

    def test_mark_seen(self):
        intent = (OrderIntent()
                  .with_flow_id("FLOW-001")
                  .with_symbol("NVDA")
                  .with_side(Side.BUY)
                  .with_quantity(1000)
                  .with_account_id("ACC-001"))
        fp = OrderFingerprint.compute(intent)
        self.assertFalse(fp.is_duplicate())
        fp.mark_seen("RES-001")
        self.assertTrue(fp.is_duplicate())

    def test_from_idempotency_key(self):
        fp = OrderFingerprint.from_idempotency_key("FLOW-001:ORDER-001")
        self.assertEqual(len(fp.fingerprint), 64)

    def test_get_previous_result(self):
        intent = (OrderIntent()
                  .with_flow_id("FLOW-001")
                  .with_symbol("NVDA")
                  .with_side(Side.BUY)
                  .with_quantity(1000)
                  .with_account_id("ACC-001"))
        fp = OrderFingerprint.compute(intent)
        self.assertIsNone(fp.get_previous_result())
        fp.mark_seen("RES-001")
        self.assertEqual(fp.get_previous_result(), "RES-001")

    def test_to_dict(self):
        intent = (OrderIntent()
                  .with_flow_id("FLOW-001")
                  .with_account_id("ACC-001")
                  .with_symbol("NVDA")
                  .with_side(Side.BUY)
                  .with_quantity(1000))
        fp = OrderFingerprint.compute(intent)
        d = fp.to_dict()
        self.assertEqual(d["intent_id"], intent.intent_id)


if __name__ == "__main__":
    unittest.main()
