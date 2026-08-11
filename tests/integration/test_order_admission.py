"""Tests for OrderAdmission: full pipeline admit/reject/block/duplicate scenarios."""

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
from services.integration.order_admission import OrderAdmission
from services.integration.admission_request import AdmissionRequest
from services.integration.admission_result import AdmissionResultStatus
from services.integration.admission_policy import AdmissionPolicy


class TestOrderAdmission(unittest.TestCase):

    def setUp(self):
        self.admission = OrderAdmission()
        self.admission.reservation.set_balance("ACC-001", 10000000.0)
        self.intent = (OrderIntent()
                       .with_flow_id("FLOW-001")
                       .with_decision_id("DEC-001")
                       .with_strategy_id("STRAT-001")
                       .with_portfolio_id("PORT-001")
                       .with_account_id("ACC-001")
                       .with_symbol("NVDA")
                       .with_side(Side.BUY)
                       .with_quantity(1000)
                       .with_order_type(OrderType.LIMIT)
                       .with_limit_price(180.0))

    def _make_request(self, **kw):
        req = (AdmissionRequest.from_intent(self.intent)
               .with_risk_result(True, "RISK-001")
               .with_governance_result(True, "GOV-001", state="NORMAL")
               .with_authority_result(True, "AUTH-001", authority_id="AUTH-001", limit=500000)
               .with_approval_result(True, "APR-001", approval_id="APR-001",
                                     status="APPROVED", amount=300000,
                                     expiry=time.time() + 3600))
        if kw.get("policy_version"):
            req.policy_version = kw["policy_version"]
        if kw.get("approval_policy_version"):
            req.approval_policy_version = kw["approval_policy_version"]
        return req

    def test_full_pipeline_admitted(self):
        req = self._make_request(
            policy_version="POLICY-v1", approval_policy_version="POLICY-v1"
        )
        result = self.admission.admit(req)
        self.assertEqual(result.status, AdmissionResultStatus.ADMITTED)
        self.assertEqual(result.code, "ORDER_ADMITTED")
        self.assertTrue(result.order_id)
        self.assertTrue(result.certificate_id)
        self.assertTrue(self.admission.registry.is_admitted("FLOW-001"))

    def test_validation_failure_rejects(self):
        intent = (OrderIntent()
                  .with_flow_id("FLOW-001")
                  .with_decision_id("DEC-001")
                  .with_strategy_id("STRAT-001")
                  .with_account_id("ACC-001")
                  .with_symbol("")  # missing symbol
                  .with_side(Side.BUY)
                  .with_quantity(1000))
        req = AdmissionRequest(intent=intent)
        result = self.admission.admit(req)
        self.assertEqual(result.status, AdmissionResultStatus.REJECTED)

    def test_missing_intent_rejected(self):
        req = AdmissionRequest(intent=None)
        result = self.admission.admit(req)
        self.assertEqual(result.status, AdmissionResultStatus.REJECTED)

    def test_governance_frozen_blocked(self):
        req = (AdmissionRequest.from_intent(self.intent)
               .with_governance_result(True, state="FROZEN"))
        result = self.admission.admit(req)
        self.assertEqual(result.status, AdmissionResultStatus.BLOCKED)

    def test_reservation_failure(self):
        self.admission.reservation.set_balance("ACC-001", 1000.0)  # tiny balance
        req = self._make_request(
            policy_version="POLICY-v1", approval_policy_version="POLICY-v1"
        )
        result = self.admission.admit(req)
        self.assertEqual(result.status, AdmissionResultStatus.RESERVATION_FAILED)

    def test_duplicate_detection(self):
        req = self._make_request(
            policy_version="POLICY-v1", approval_policy_version="POLICY-v1"
        )
        # First submission
        result1 = self.admission.admit(req)
        self.assertEqual(result1.status, AdmissionResultStatus.ADMITTED)

        # Second submission with same intent
        req2 = self._make_request(
            policy_version="POLICY-v1", approval_policy_version="POLICY-v1"
        )
        result2 = self.admission.admit(req2)
        self.assertEqual(result2.status, AdmissionResultStatus.DUPLICATE)

    def test_metrics_tracking(self):
        req = self._make_request(
            policy_version="POLICY-v1", approval_policy_version="POLICY-v1"
        )
        self.admission.admit(req)
        self.assertEqual(self.admission.metrics.total_received, 1)
        self.assertEqual(self.admission.metrics.total_admitted, 1)
        self.assertGreater(self.admission.metrics.get_overall_pass_rate(), 0)

    def test_to_dict(self):
        d = self.admission.to_dict()
        self.assertIn("policy", d)
        self.assertIn("registry", d)
        self.assertIn("metrics", d)


class TestOrderAdmissionPolicyVersion(unittest.TestCase):

    def setUp(self):
        self.admission = OrderAdmission()
        self.admission.reservation.set_balance("ACC-001", 10000000.0)
        self.intent = (OrderIntent()
                       .with_flow_id("FLOW-001")
                       .with_decision_id("DEC-001")
                       .with_strategy_id("STRAT-001")
                       .with_account_id("ACC-001")
                       .with_symbol("NVDA")
                       .with_side(Side.BUY)
                       .with_quantity(1000)
                       .with_order_type(OrderType.LIMIT)
                       .with_limit_price(180.0))

    def test_policy_version_mismatch_blocks(self):
        req = (AdmissionRequest.from_intent(self.intent)
               .with_governance_result(True, state="NORMAL")
               .with_authority_result(True, authority_id="AUTH-001", limit=500000)
               .with_approval_result(True, approval_id="APR-001",
                                     status="APPROVED", amount=300000,
                                     expiry=time.time() + 3600))
        req.policy_version = "POLICY-v8"
        req.approval_policy_version = "POLICY-v7"
        result = self.admission.admit(req)
        self.assertEqual(result.status, AdmissionResultStatus.BLOCKED)


if __name__ == "__main__":
    unittest.main()
