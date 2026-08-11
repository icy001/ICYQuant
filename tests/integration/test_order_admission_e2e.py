"""End-to-end tests: full Signal → Decision → Risk → Gov → Auth → Approval → Admission → OMS chain."""

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
from services.integration.admission_policy import AdmissionPolicy, EmergencyAdmissionPolicy
from services.integration.admission_gate import AdmissionGate
from services.integration.order_certificate import CertificateStatus


class TestE2EHappyPath(unittest.TestCase):
    """Full happy path: Signal → Decision → All gates → Admission → Certificate → OMS."""

    def setUp(self):
        self.admission = OrderAdmission()
        self.admission.reservation.set_balance("ACC-001", 10000000.0)

    def _build_request(self, flow_id="FLOW-001", symbol="NVDA", quantity=1000,
                       price=180.0, side=Side.BUY):
        intent = (OrderIntent()
                  .with_flow_id(flow_id)
                  .with_decision_id(f"DEC-{flow_id}")
                  .with_strategy_id("STRAT-001")
                  .with_portfolio_id("PORT-001")
                  .with_account_id("ACC-001")
                  .with_symbol(symbol)
                  .with_side(side)
                  .with_quantity(quantity)
                  .with_order_type(OrderType.LIMIT)
                  .with_limit_price(price))
        return (AdmissionRequest.from_intent(intent)
                .with_risk_result(True, "RISK-RSP-001")
                .with_governance_result(True, "GOV-RSP-001", state="NORMAL")
                .with_authority_result(True, "AUTH-RSP-001", authority_id="AUTH-001",
                                       limit=500000)
                .with_approval_result(True, "APR-RSP-001", approval_id="APR-001",
                                      status="APPROVED", amount=300000,
                                      expiry=time.time() + 86400))

    def test_full_happy_path(self):
        """E2E: valid intent → all checks pass → admitted → certificate valid for OMS."""
        req = self._build_request()
        req.policy_version = "POLICY-v1"
        req.approval_policy_version = "POLICY-v1"

        result = self.admission.admit(req)
        self.assertEqual(result.status, AdmissionResultStatus.ADMITTED,
                         f"Expected ADMITTED but got {result.status.label}: {result.message}")

        # Certificate was issued
        self.assertTrue(result.certificate_id)
        cert = self.admission.registry.get_by_certificate(result.certificate_id)
        self.assertIsNotNone(cert)
        self.assertIsNotNone(cert.certificate)

        # OMS gate check
        gate = AdmissionGate()
        gate_result = gate.validate_for_oms(cert.certificate, req.intent)
        self.assertTrue(gate_result.passed, f"Gate should pass but got: {gate_result.code}")

        # Metrics reflect the admission
        self.assertEqual(self.admission.metrics.total_admitted, 1)

    def test_e2e_what_if_ordered_is_modified_after_certificate(self):
        """Security boundary: modifying order after certificate → OMS rejects."""
        req = self._build_request()
        req.policy_version = "POLICY-v1"
        req.approval_policy_version = "POLICY-v1"
        result = self.admission.admit(req)
        self.assertEqual(result.status, AdmissionResultStatus.ADMITTED)

        cert_record = self.admission.registry.get_by_certificate(result.certificate_id)
        certificate = cert_record.certificate

        # Attacker modifies intent
        tampered = (OrderIntent()
                    .with_flow_id("FLOW-001")
                    .with_account_id("ACC-001")
                    .with_symbol("NVDA")
                    .with_side(Side.BUY)
                    .with_quantity(10000)  # Changed from 1000 to 10000!
                    .with_order_type(OrderType.LIMIT)
                    .with_limit_price(180.0))

        gate = AdmissionGate()
        gate_result = gate.validate_for_oms(certificate, tampered)
        self.assertFalse(gate_result.passed)
        self.assertEqual(gate_result.code, "CERTIFICATE_MISMATCH")


class TestE2EErrorScenarios(unittest.TestCase):
    """E2E error scenarios: risk failure, governance freeze, authority expired, etc."""

    def setUp(self):
        self.admission = OrderAdmission()
        self.admission.reservation.set_balance("ACC-001", 10000000.0)

    def _make_intent(self):
        return (OrderIntent()
                .with_flow_id("FLOW-E2E")
                .with_decision_id("DEC-E2E")
                .with_strategy_id("STRAT-001")
                .with_account_id("ACC-001")
                .with_symbol("NVDA")
                .with_side(Side.BUY)
                .with_quantity(1000)
                .with_order_type(OrderType.LIMIT)
                .with_limit_price(180.0))

    def test_governance_freeze_e2e(self):
        """Governance FROZEN → BLOCKED even if everything else passes."""
        intent = self._make_intent()
        req = (AdmissionRequest.from_intent(intent)
               .with_risk_result(True)
               .with_governance_result(True, state="FROZEN"))
        result = self.admission.admit(req)
        self.assertEqual(result.status, AdmissionResultStatus.BLOCKED)

    def test_authority_expired_e2e(self):
        """Authority expired → BLOCKED."""
        intent = self._make_intent()
        req = (AdmissionRequest.from_intent(intent)
               .with_risk_result(True)
               .with_governance_result(True, state="NORMAL")
               .with_authority_result(True, authority_id="AUTH-001", limit=500000))
        req.authority_expiry = time.time() - 3600
        result = self.admission.admit(req)
        self.assertEqual(result.status, AdmissionResultStatus.BLOCKED)

    def test_approval_expired_e2e(self):
        """Approval expired → BLOCKED."""
        intent = self._make_intent()
        req = (AdmissionRequest.from_intent(intent)
               .with_risk_result(True)
               .with_governance_result(True, state="NORMAL")
               .with_authority_result(True, authority_id="AUTH-001", limit=500000)
               .with_approval_result(True, status="APPROVED",
                                     expiry=time.time() - 3600))
        result = self.admission.admit(req)
        self.assertEqual(result.status, AdmissionResultStatus.BLOCKED)

    def test_policy_mismatch_e2e(self):
        """Policy version mismatch → BLOCKED."""
        intent = self._make_intent()
        req = (AdmissionRequest.from_intent(intent)
               .with_risk_result(True)
               .with_governance_result(True, state="NORMAL")
               .with_authority_result(True, authority_id="AUTH-001", limit=500000)
               .with_approval_result(True, approval_id="APR-001",
                                     status="APPROVED", amount=300000,
                                     expiry=time.time() + 86400))
        req.policy_version = "POLICY-v8"
        req.approval_policy_version = "POLICY-v7"
        result = self.admission.admit(req)
        self.assertEqual(result.status, AdmissionResultStatus.BLOCKED)

    def test_duplicate_order_e2e(self):
        """Duplicate submission → DUPLICATE."""
        intent = self._make_intent()
        req1 = (AdmissionRequest.from_intent(intent)
                .with_risk_result(True)
                .with_governance_result(True, state="NORMAL")
                .with_authority_result(True, authority_id="AUTH-001", limit=500000)
                .with_approval_result(True, approval_id="APR-001",
                                      status="APPROVED", amount=300000,
                                      expiry=time.time() + 86400))
        req1.policy_version = "POLICY-v1"
        req1.approval_policy_version = "POLICY-v1"

        r1 = self.admission.admit(req1)
        self.assertEqual(r1.status, AdmissionResultStatus.ADMITTED)

        # Re-submit same
        r2 = self.admission.admit(req1)
        self.assertEqual(r2.status, AdmissionResultStatus.DUPLICATE)

    def test_reservation_failure_e2e(self):
        """Insufficient balance → RESERVATION_FAILED."""
        self.admission.reservation.set_balance("ACC-001", 1000.0)  # tiny balance
        intent = self._make_intent()
        req = (AdmissionRequest.from_intent(intent)
               .with_risk_result(True)
               .with_governance_result(True, state="NORMAL")
               .with_authority_result(True, authority_id="AUTH-001", limit=500000)
               .with_approval_result(True, approval_id="APR-001",
                                     status="APPROVED", amount=300000,
                                     expiry=time.time() + 86400))
        req.policy_version = "POLICY-v1"
        req.approval_policy_version = "POLICY-v1"
        result = self.admission.admit(req)
        self.assertEqual(result.status, AdmissionResultStatus.RESERVATION_FAILED)


class TestE2EEmergencyOrders(unittest.TestCase):

    def setUp(self):
        self.admission = OrderAdmission()
        self.admission.reservation.set_balance("ACC-001", 10000000.0)
        self.admission.policy = AdmissionPolicy.emergency()

    def test_emergency_governance_does_not_block(self):
        """Emergency mode: even with FROZEN state, some orders may pass."""
        intent = (OrderIntent()
                  .with_flow_id("FLOW-EMERG")
                  .with_decision_id("DEC-EMERG")
                  .with_strategy_id("STRAT-001")
                  .with_account_id("ACC-001")
                  .with_symbol("NVDA")
                  .with_side(Side.SELL)
                  .with_quantity(1000)
                  .with_order_type(OrderType.LIMIT)
                  .with_limit_price(180.0))
        req = (AdmissionRequest.from_intent(intent)
               .with_emergency()
               .with_governance_result(True, state="EMERGENCY")
               .with_authority_result(True, authority_id="AUTH-001", limit=500000)
               .with_approval_result(True, approval_id="APR-001",
                                     status="APPROVED", amount=300000,
                                     expiry=time.time() + 86400))
        req.policy_version = "POLICY-v1"
        req.approval_policy_version = "POLICY-v1"

        # Under emergency policy, governance check is not required
        self.assertFalse(self.admission.policy.governance_check_required)

        result = self.admission.admit(req)
        self.assertIn(result.status, [
            AdmissionResultStatus.ADMITTED,
            AdmissionResultStatus.RESERVATION_FAILED,  # reservation may still fail
        ])

    def test_emergency_policy_blocks_certain_intents(self):
        ep = EmergencyAdmissionPolicy()
        self.assertFalse(ep.is_allowed("NEW_RISK"))
        self.assertFalse(ep.is_allowed("INCREASE_EXPOSURE"))
        self.assertTrue(ep.is_allowed("CLOSE"))
        self.assertTrue(ep.is_allowed("HEDGE"))


class TestE2EMultiOrder(unittest.TestCase):

    def setUp(self):
        self.admission = OrderAdmission()
        self.admission.reservation.set_balance("ACC-001", 10000000.0)
        self.gate = AdmissionGate()

    def _submit(self, flow_id, symbol, quantity, price):
        intent = (OrderIntent()
                  .with_flow_id(flow_id)
                  .with_decision_id(f"DEC-{flow_id}")
                  .with_strategy_id("STRAT-001")
                  .with_account_id("ACC-001")
                  .with_symbol(symbol)
                  .with_side(Side.BUY)
                  .with_quantity(quantity)
                  .with_order_type(OrderType.LIMIT)
                  .with_limit_price(price))
        req = (AdmissionRequest.from_intent(intent)
               .with_risk_result(True)
               .with_governance_result(True, state="NORMAL")
               .with_authority_result(True, authority_id="AUTH-001", limit=500000)
               .with_approval_result(True, approval_id="APR-001",
                                     status="APPROVED", amount=300000,
                                     expiry=time.time() + 86400))
        req.policy_version = "POLICY-v1"
        req.approval_policy_version = "POLICY-v1"
        return self.admission.admit(req)

    def test_multiple_orders_different_flow_ids(self):
        r1 = self._submit("FLOW-10", "NVDA", 1000, 180.0)
        r2 = self._submit("FLOW-11", "AAPL", 500, 200.0)
        self.assertEqual(r1.status, AdmissionResultStatus.ADMITTED)
        self.assertEqual(r2.status, AdmissionResultStatus.ADMITTED)
        self.assertEqual(self.admission.metrics.total_admitted, 2)

        # Both certificates should be valid
        for flow_id in ["FLOW-10", "FLOW-11"]:
            record = self.admission.registry.get_by_flow(flow_id)
            self.assertIsNotNone(record)
            self.assertEqual(record.result.status, AdmissionResultStatus.ADMITTED)


if __name__ == "__main__":
    unittest.main()
