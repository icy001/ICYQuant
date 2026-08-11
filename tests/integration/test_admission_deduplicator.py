"""Tests for AdmissionDeduplicator: fingerprint-based + idempotency-key duplicate detection."""

from __future__ import annotations

import sys
import os
import time
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
from services.integration.admission_deduplicator import AdmissionDeduplicator
from services.integration.admission_result import AdmissionResult


class TestAdmissionDeduplicator(unittest.TestCase):

    def setUp(self):
        self.dedup = AdmissionDeduplicator()
        self.intent = (OrderIntent()
                       .with_flow_id("FLOW-001")
                       .with_account_id("ACC-001")
                       .with_symbol("NVDA")
                       .with_side(Side.BUY)
                       .with_quantity(1000))

    def test_first_submission_not_duplicate(self):
        result = self.dedup.check_duplicate(self.intent)
        self.assertFalse(result.is_duplicate)

    def test_second_identical_submission_is_duplicate(self):
        self.dedup.check_duplicate(self.intent)
        result = self.dedup.check_duplicate(self.intent)
        self.assertTrue(result.is_duplicate)

    def test_different_quantity_not_duplicate(self):
        self.dedup.check_duplicate(self.intent)
        intent2 = (OrderIntent()
                   .with_flow_id("FLOW-001")
                   .with_account_id("ACC-001")
                   .with_symbol("NVDA")
                   .with_side(Side.BUY)
                   .with_quantity(2000))
        result = self.dedup.check_duplicate(intent2)
        self.assertFalse(result.is_duplicate)

    def test_idempotency_key_returns_cached_result(self):
        result = AdmissionResult.make_admitted(
            flow_id="FLOW-001", intent_id=self.intent.intent_id,
            order_id="ORDER-001", certificate_id="CERT-001",
        )
        self.dedup.store_idempotency_result("FLOW-001:ORDER-001", result)

        cached = self.dedup.get_idempotency_result("FLOW-001:ORDER-001")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["order_id"], "ORDER-001")

    def test_idempotency_key_duplicate_detection(self):
        result = AdmissionResult.make_admitted(
            flow_id="FLOW-001", intent_id=self.intent.intent_id,
            order_id="ORDER-001", certificate_id="CERT-001",
        )
        self.dedup.store_idempotency_result("FLOW-001:ORDER-001", result)

        dup = self.dedup.check_duplicate(self.intent, "FLOW-001:ORDER-001")
        self.assertTrue(dup.is_duplicate)

    def test_idempotency_expired(self):
        self.dedup.idempotency_ttl = 0.001  # TTL in seconds
        result = AdmissionResult.make_admitted(
            flow_id="FLOW-001", intent_id=self.intent.intent_id,
            order_id="ORDER-001", certificate_id="CERT-001",
        )
        self.dedup.store_idempotency_result("FLOW-001:ORDER-001", result)

        time.sleep(0.01)  # ensure entry expires
        cached = self.dedup.get_idempotency_result("FLOW-001:ORDER-001")
        self.assertIsNone(cached)

    def test_reset_clears_state(self):
        self.dedup.check_duplicate(self.intent)
        self.dedup.reset()
        result = self.dedup.check_duplicate(self.intent)
        self.assertFalse(result.is_duplicate)


if __name__ == "__main__":
    unittest.main()
