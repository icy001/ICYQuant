"""Tests for AdmissionAuthorizer: governance, authority, approval, policy version checks."""

from __future__ import annotations

import sys
import os
import types
import importlib.util
import time
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
from services.integration.admission_request import AdmissionRequest
from services.integration.admission_authorizer import AdmissionAuthorizer
from services.integration.admission_policy import AdmissionPolicy


class TestAdmissionAuthorizer(unittest.TestCase):

    def setUp(self):
        self.authorizer = AdmissionAuthorizer(policy=AdmissionPolicy.standard())
        self.intent = (OrderIntent()
                       .with_flow_id("FLOW-001")
                       .with_account_id("ACC-001")
                       .with_symbol("NVDA")
                       .with_side(Side.BUY)
                       .with_quantity(1000)
                       .with_limit_price(180.0)
                       .with_order_type(OrderType.LIMIT))

    def test_all_checks_pass(self):
        req = (AdmissionRequest.from_intent(self.intent)
               .with_governance_result(True, state="NORMAL")
               .with_authority_result(True, authority_id="AUTH-001", limit=500000)
               .with_approval_result(True, approval_id="APR-001", status="APPROVED",
                                     amount=300000, expiry=time.time() + 3600))
        report = self.authorizer.authorize(req)
        self.assertTrue(report.authorized)

    def test_governance_frozen_blocks(self):
        req = (AdmissionRequest.from_intent(self.intent)
               .with_governance_result(True, state="FROZEN"))
        report = self.authorizer.authorize(req)
        self.assertFalse(report.authorized)
        self.assertTrue(any(c.code == "GOVERNANCE_FROZEN" for c in report.checks))

    def test_governance_emergency_blocks_non_emergency(self):
        req = (AdmissionRequest.from_intent(self.intent)
               .with_governance_result(True, state="EMERGENCY"))
        report = self.authorizer.authorize(req)
        self.assertFalse(report.authorized)
        self.assertTrue(any(c.code == "GOVERNANCE_EMERGENCY" for c in report.checks))

    def test_authority_revoked_blocks(self):
        req = (AdmissionRequest.from_intent(self.intent)
               .with_governance_result(True, state="NORMAL")
               .with_authority_result(True, authority_id="AUTH-001"))
        req.authority_revoked = True
        report = self.authorizer.authorize(req)
        self.assertFalse(report.authorized)
        self.assertTrue(any(c.code == "AUTHORITY_REVOKED" for c in report.checks))

    def test_authority_expired_blocks(self):
        req = (AdmissionRequest.from_intent(self.intent)
               .with_governance_result(True, state="NORMAL")
               .with_authority_result(True, authority_id="AUTH-001", limit=500000))
        req.authority_expiry = time.time() - 3600  # expired 1 hour ago
        report = self.authorizer.authorize(req)
        self.assertFalse(report.authorized)
        self.assertTrue(any(c.code == "AUTHORITY_EXPIRED" for c in report.checks))

    def test_authority_limit_exceeded(self):
        req = (AdmissionRequest.from_intent(self.intent)
               .with_governance_result(True, state="NORMAL")
               .with_authority_result(True, authority_id="AUTH-001", limit=10000))
        # Notional = 1000 * 180 = 180000 > 10000
        report = self.authorizer.authorize(req)
        self.assertFalse(report.authorized)
        self.assertTrue(any(c.code == "AUTHORITY_LIMIT_EXCEEDED" for c in report.checks))

    def test_approval_not_approved(self):
        req = (AdmissionRequest.from_intent(self.intent)
               .with_governance_result(True, state="NORMAL")
               .with_authority_result(True, authority_id="AUTH-001", limit=500000)
               .with_approval_result(True, approval_id="APR-001", status="PENDING"))
        report = self.authorizer.authorize(req)
        self.assertFalse(report.authorized)
        self.assertTrue(any(c.code == "APPROVAL_NOT_APPROVED" for c in report.checks))

    def test_approval_expired(self):
        req = (AdmissionRequest.from_intent(self.intent)
               .with_governance_result(True, state="NORMAL")
               .with_authority_result(True, authority_id="AUTH-001", limit=500000)
               .with_approval_result(True, approval_id="APR-001", status="APPROVED",
                                     expiry=time.time() - 3600))
        report = self.authorizer.authorize(req)
        self.assertFalse(report.authorized)
        self.assertTrue(any(c.code == "APPROVAL_EXPIRED" for c in report.checks))

    def test_policy_version_mismatch(self):
        req = (AdmissionRequest.from_intent(self.intent)
               .with_governance_result(True, state="NORMAL")
               .with_authority_result(True, authority_id="AUTH-001", limit=500000)
               .with_approval_result(True, approval_id="APR-001", status="APPROVED",
                                     amount=300000, expiry=time.time() + 3600))
        req.policy_version = "POLICY-v8"
        req.approval_policy_version = "POLICY-v7"
        report = self.authorizer.authorize(req)
        self.assertFalse(report.authorized)
        self.assertTrue(any(c.code == "POLICY_VERSION_MISMATCH" for c in report.checks))

    def test_policy_version_match(self):
        req = (AdmissionRequest.from_intent(self.intent)
               .with_governance_result(True, state="NORMAL")
               .with_authority_result(True, authority_id="AUTH-001", limit=500000)
               .with_approval_result(True, approval_id="APR-001", status="APPROVED",
                                     amount=300000, expiry=time.time() + 3600))
        req.policy_version = "POLICY-v8"
        req.approval_policy_version = "POLICY-v8"
        report = self.authorizer.authorize(req)
        self.assertTrue(report.authorized)


if __name__ == "__main__":
    unittest.main()
