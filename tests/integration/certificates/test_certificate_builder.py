"""Tests for CertificateBuilder — assembly of PreTradeControlCertificate from control evidence."""

from __future__ import annotations

import sys
import os
import types
import importlib.util
import unittest

_ws = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_int_dir = os.path.join(_ws, "services", "integration")
_cert_dir = os.path.join(_int_dir, "certificates")

if "services" not in sys.modules:
    _svc = types.ModuleType("services"); _svc.__path__ = [os.path.join(_ws, "services")]
    sys.modules["services"] = _svc
if "services.integration" not in sys.modules:
    _mod = types.ModuleType("services.integration"); _mod.__path__ = [_int_dir]
    sys.modules["services.integration"] = _mod
if "services.integration.certificates" not in sys.modules:
    _pkg = types.ModuleType("services.integration.certificates"); _pkg.__path__ = [_cert_dir]
    sys.modules["services.integration.certificates"] = _pkg

for _name in [
    "certificate_errors", "certificate_status", "certificate_scope",
    "certificate_claim", "certificate_evidence", "certificate_signature",
    "certificate_fingerprint", "pre_trade_certificate", "certificate_builder",
    "certificate_validator", "certificate_verifier",
]:
    _fp = os.path.join(_cert_dir, f"{_name}.py")
    if not os.path.exists(_fp): continue
    _mod_name = f"services.integration.certificates.{_name}"
    if _mod_name in sys.modules: continue
    _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
    _m = importlib.util.module_from_spec(_spec)
    sys.modules[_mod_name] = _m
    _spec.loader.exec_module(_m)

for _name in ["certificate_lifecycle", "certificate_registry", "certificate_metrics"]:
    _fp = os.path.join(_int_dir, f"{_name}.py")
    if not os.path.exists(_fp): continue
    _mod_name = f"services.integration.{_name}"
    if _mod_name in sys.modules: continue
    _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
    _m = importlib.util.module_from_spec(_spec)
    sys.modules[_mod_name] = _m
    _spec.loader.exec_module(_m)

from services.integration.certificates.certificate_builder import CertificateBuilder
from services.integration.certificates.certificate_status import CertificateStatus
from services.integration.certificates.certificate_scope import ConsumptionMode


class TestCertificateBuilderBasic(unittest.TestCase):

    def setUp(self):
        self.builder = CertificateBuilder()

    def test_build_empty(self):
        cert = self.builder.build()
        self.assertTrue(cert.certificate_id.startswith("CERT-"))
        self.assertEqual(cert.status, CertificateStatus.ISSUED)

    def test_build_with_flow(self):
        cert = (self.builder
                .with_flow_id("FLOW-001")
                .with_decision_id("DEC-001")
                .build())
        self.assertEqual(cert.flow_id, "FLOW-001")
        self.assertEqual(cert.decision_id, "DEC-001")


class TestCertificateBuilderFullPipeline(unittest.TestCase):
    """Build a complete certificate with all gates passed."""

    def setUp(self):
        self.builder = CertificateBuilder()
        self.builder.with_flow_id("FLOW-001")
        self.builder.with_decision_id("DEC-001")
        self.builder.with_signal_id("SIG-001")
        self.builder.with_strategy_id("STRAT-001")
        self.builder.with_order_intent(
            intent_id="INTENT-001", intent_hash="abc123hash",
            account_id="ACC-001", portfolio_id="PORT-001",
        )
        self.builder.with_symbol("NVDA")
        self.builder.with_side("BUY")
        self.builder.with_venue("NASDAQ")
        self.builder.with_order_type("LIMIT")
        self.builder.with_quantity(1000)
        self.builder.with_limit_price(180.0)
        self.builder.with_max_notional(200000.0)
        self.builder.with_risk_decision(True, policy_version="RISK-v8",
                                         detail={"exposure": 0.12})
        self.builder.with_governance_decision(True, state="NORMAL",
                                              policy_version="GOV-v5")
        self.builder.with_authority_decision(True, authority_id="AUTH-001",
                                             limit=500000, policy_version="AUTH-v3")
        self.builder.with_approval_decision(True, approval_id="APR-001",
                                            status="APPROVED", amount=180000,
                                            policy_version="APPROVAL-v2")
        self.builder.with_effective_constraints({
            "max_quantity": 1000, "max_leverage": 2,
        })

    def test_build_produces_valid_certificate(self):
        cert = self.builder.build()
        self.assertIsNotNone(cert.risk_claim)
        self.assertIsNotNone(cert.governance_claim)
        self.assertIsNotNone(cert.authority_claim)
        self.assertIsNotNone(cert.approval_claim)
        self.assertTrue(cert.all_claims_passed())

    def test_build_and_seal(self):
        cert = self.builder.build_and_seal()
        self.assertEqual(cert.status, CertificateStatus.VALID)
        self.assertIsNotNone(cert.fingerprint)
        self.assertIsNotNone(cert.signature)

    def test_builder_evidence_present(self):
        cert = self.builder.build()
        self.assertTrue(len(cert.evidence) >= 4)

    def test_builder_policy_versions_locked(self):
        cert = self.builder.build()
        self.assertIn("risk", cert.policy_versions)
        self.assertIn("governance", cert.policy_versions)
        self.assertIn("authority", cert.policy_versions)
        self.assertIn("approval", cert.policy_versions)

    def test_builder_scope_bound(self):
        cert = self.builder.build()
        self.assertEqual(cert.scope.symbol, "NVDA")
        self.assertEqual(cert.scope.side, "BUY")
        self.assertEqual(cert.scope.max_quantity, 1000)


class TestCertificateBuilderConstraints(unittest.TestCase):

    def test_effective_constraints_immutable_after_build(self):
        builder = CertificateBuilder()
        builder.with_flow_id("FLOW-001")
        builder.with_effective_constraints({"max_leverage": 2, "max_quantity": 1000})
        cert = builder.build()
        self.assertIn("max_quantity", cert.effective_constraints)
        self.assertEqual(cert.effective_constraints["max_quantity"], 1000)

    def test_empty_constraints(self):
        builder = CertificateBuilder()
        builder.with_flow_id("FLOW-001")
        cert = builder.build()
        self.assertEqual(cert.effective_constraints, {})


class TestCertificateBuilderTTL(unittest.TestCase):

    def test_default_ttl(self):
        builder = CertificateBuilder()
        builder.with_flow_id("FLOW-001")
        cert = builder.build()
        self.assertIsNotNone(cert.expires_at)
        self.assertGreater(cert.expires_at, cert.issued_at)

    def test_custom_ttl(self):
        builder = CertificateBuilder()
        builder.with_flow_id("FLOW-001")
        builder.with_ttl(60.0)
        cert = builder.build()
        expected = cert.issued_at + 60
        self.assertAlmostEqual(cert.expires_at, expected, delta=1)


class TestBuilderCannotOverrideGateDecisions(unittest.TestCase):
    """Builder assembles evidence, does not make decisions."""

    def test_failed_gates_recorded_as_failed(self):
        builder = CertificateBuilder().with_flow_id("FLOW-001")
        builder.with_risk_decision(False)
        cert = builder.build()
        self.assertFalse(cert.risk_claim.is_pass())

    def test_mixed_results(self):
        builder = CertificateBuilder().with_flow_id("FLOW-001")
        builder.with_risk_decision(True)
        builder.with_governance_decision(False, state="FROZEN")
        cert = builder.build()
        self.assertTrue(cert.risk_claim.is_pass())
        self.assertFalse(cert.governance_claim.is_pass())
        self.assertFalse(cert.all_claims_passed())


if __name__ == "__main__":
    unittest.main()
