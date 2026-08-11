"""Tests for OrderCertificate: creation, validation, hash verification, tamper detection."""

from __future__ import annotations

import sys
import os
import types
import importlib.util
import time
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
from services.integration.order_constraints import OrderConstraints
from services.integration.order_certificate import OrderCertificate, CertificateStatus


class TestOrderCertificate(unittest.TestCase):
    """Test certificate creation and validation."""

    def setUp(self):
        self.intent_dict = {
            "intent_id": "INTENT-001",
            "flow_id": "FLOW-001",
            "symbol": "NVDA",
            "side": "BUY",
            "quantity": 1000,
            "limit_price": 180.0,
        }
        self.constraints_dict = {"max_notional": 200000}
        self.policy_dict = {}

    def test_create_certificate(self):
        cert = OrderCertificate.create(
            intent=self.intent_dict,
            constraints=self.constraints_dict,
            policy=self.policy_dict,
            fingerprint="abc123",
            flow_id="FLOW-001",
            order_id="ORDER-001",
            ttl_seconds=300,
        )
        self.assertEqual(cert.flow_id, "FLOW-001")
        self.assertEqual(cert.order_id, "ORDER-001")
        self.assertEqual(cert.status, CertificateStatus.VALID)
        self.assertIsNotNone(cert.expires_at)
        self.assertTrue(len(cert.intent_hash) == 64)

    def test_verify_intent_match(self):
        cert = OrderCertificate.create(
            intent=self.intent_dict, constraints=self.constraints_dict,
            policy=self.policy_dict, fingerprint="abc123",
        )
        self.assertTrue(cert.verify_intent(self.intent_dict))

    def test_verify_intent_mismatch(self):
        cert = OrderCertificate.create(
            intent=self.intent_dict, constraints=self.constraints_dict,
            policy=self.policy_dict, fingerprint="abc123",
        )
        modified = dict(self.intent_dict)
        modified["quantity"] = 2000
        self.assertFalse(cert.verify_intent(modified))

    def test_verify_constraints_match(self):
        cert = OrderCertificate.create(
            intent=self.intent_dict, constraints=self.constraints_dict,
            policy=self.policy_dict, fingerprint="abc123",
        )
        self.assertTrue(cert.verify_constraints(self.constraints_dict))

    def test_verify_constraints_mismatch(self):
        cert = OrderCertificate.create(
            intent=self.intent_dict, constraints=self.constraints_dict,
            policy=self.policy_dict, fingerprint="abc123",
        )
        modified = dict(self.constraints_dict)
        modified["max_notional"] = 999999
        self.assertFalse(cert.verify_constraints(modified))

    def test_is_not_expired_when_new(self):
        cert = OrderCertificate.create(
            intent=self.intent_dict, constraints=self.constraints_dict,
            policy=self.policy_dict, fingerprint="abc123",
        )
        self.assertFalse(cert.is_expired())

    def test_is_expired_after_ttl(self):
        cert = OrderCertificate.create(
            intent=self.intent_dict, constraints=self.constraints_dict,
            policy=self.policy_dict, fingerprint="abc123",
            ttl_seconds=0,
        )
        time.sleep(0.01)
        self.assertTrue(cert.is_expired())

    def test_validate_returns_valid(self):
        cert = OrderCertificate.create(
            intent=self.intent_dict, constraints=self.constraints_dict,
            policy=self.policy_dict, fingerprint="abc123",
        )
        self.assertEqual(cert.validate(), CertificateStatus.VALID)

    def test_validate_detects_expired(self):
        cert = OrderCertificate.create(
            intent=self.intent_dict, constraints=self.constraints_dict,
            policy=self.policy_dict, fingerprint="abc123",
            ttl_seconds=0,
        )
        time.sleep(0.01)
        self.assertEqual(cert.validate(), CertificateStatus.EXPIRED)

    def test_to_dict(self):
        cert = OrderCertificate.create(
            intent=self.intent_dict, constraints=self.constraints_dict,
            policy=self.policy_dict, fingerprint="abc123",
            flow_id="FLOW-001", order_id="ORDER-001",
        )
        d = cert.to_dict()
        self.assertEqual(d["flow_id"], "FLOW-001")
        self.assertEqual(d["status"], "VALID")


if __name__ == "__main__":
    unittest.main()
