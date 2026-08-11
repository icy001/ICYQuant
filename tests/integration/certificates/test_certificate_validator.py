"""Tests for CertificateValidator — structural/format validation."""

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
from services.integration.certificates.certificate_validator import CertificateValidator
from services.integration.certificates.pre_trade_certificate import PreTradeControlCertificate


def _build_valid_cert():
    return (CertificateBuilder()
            .with_flow_id("FLOW-001")
            .with_decision_id("DEC-001")
            .with_strategy_id("STRAT-001")
            .with_order_intent(intent_id="INTENT-001", intent_hash="abc",
                               account_id="ACC-001")
            .with_symbol("NVDA").with_side("BUY")
            .with_quantity(1000)
            .with_risk_decision(True, policy_version="RISK-v8")
            .with_governance_decision(True, state="NORMAL", policy_version="GOV-v5")
            .with_authority_decision(True, authority_id="AUTH-001", limit=500000,
                                     policy_version="AUTH-v3")
            .with_approval_decision(True, approval_id="APR-001", status="APPROVED",
                                    policy_version="APPROVAL-v2")
            .with_effective_constraints({"max_quantity": 1000})
            .build_and_seal())


class TestCertificateValidator(unittest.TestCase):

    def setUp(self):
        self.validator = CertificateValidator()

    def test_valid_sealed_certificate(self):
        cert = _build_valid_cert()
        report = self.validator.validate(cert)
        self.assertTrue(report.valid, f"Errors: {report.errors}")

    def test_missing_certificate_id(self):
        cert = PreTradeControlCertificate(certificate_id="")
        report = self.validator.validate(cert)
        self.assertFalse(report.valid)

    def test_missing_flow_id(self):
        cert = PreTradeControlCertificate(flow_id="")
        report = self.validator.validate(cert)
        self.assertFalse(report.valid)

    def test_missing_intent_id(self):
        cert = PreTradeControlCertificate(order_intent_id="")
        report = self.validator.validate(cert)
        self.assertFalse(report.valid)

    def test_missing_claims(self):
        cert = PreTradeControlCertificate(
            flow_id="FLOW-001", order_intent_id="INTENT-001",
            account_id="ACC-001",
        )
        report = self.validator.validate(cert)
        self.assertFalse(report.valid)

    def test_missing_signature(self):
        cert = _build_valid_cert()
        cert.signature = None
        report = self.validator.validate(cert)
        self.assertFalse(report.valid)

    def test_missing_fingerprint(self):
        cert = _build_valid_cert()
        cert.fingerprint = None
        report = self.validator.validate(cert)
        self.assertFalse(report.valid)

    def test_no_evidence_gives_warning(self):
        cert = _build_valid_cert()
        cert.evidence = []
        report = self.validator.validate(cert)
        self.assertTrue(len(report.warnings) > 0)

    def test_revoked_certificate(self):
        cert = _build_valid_cert()
        cert.revoke("test_revoke")
        report = self.validator.validate(cert)
        self.assertFalse(report.valid)

    def test_expired_certificate(self):
        cert = _build_valid_cert()
        cert.expire()
        report = self.validator.validate(cert)
        self.assertFalse(report.valid)

    def test_invalid_certificate(self):
        cert = _build_valid_cert()
        cert.invalidate()
        report = self.validator.validate(cert)
        self.assertFalse(report.valid)


if __name__ == "__main__":
    unittest.main()
