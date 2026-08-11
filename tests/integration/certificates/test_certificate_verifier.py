"""Tests for CertificateVerifier — runtime verification against specific Order context."""

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
from services.integration.certificates.certificate_verifier import CertificateVerifier


def _build_valid_cert():
    return (CertificateBuilder()
            .with_flow_id("FLOW-001")
            .with_decision_id("DEC-001")
            .with_strategy_id("STRAT-001")
            .with_order_intent(intent_id="INTENT-001", intent_hash="abc123hash",
                               account_id="ACC-001")
            .with_symbol("NVDA").with_side("BUY").with_venue("NASDAQ")
            .with_order_type("LIMIT")
            .with_quantity(1000).with_limit_price(180.0)
            .with_max_notional(200000.0)
            .with_risk_decision(True, policy_version="RISK-v8")
            .with_governance_decision(True, state="NORMAL", policy_version="GOV-v5")
            .with_authority_decision(True, authority_id="AUTH-001", limit=500000,
                                     policy_version="AUTH-v3")
            .with_approval_decision(True, approval_id="APR-001", status="APPROVED",
                                    policy_version="APPROVAL-v2")
            .with_effective_constraints({"max_quantity": 1000})
            .build_and_seal())


class TestCertificateVerifier(unittest.TestCase):

    def setUp(self):
        self.verifier = CertificateVerifier()

    def test_valid_verification(self):
        cert = _build_valid_cert()
        result = self.verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="abc123hash",
            symbol="NVDA", side="BUY",
            quantity=500, notional=90000,
            venue="NASDAQ",
        )
        self.assertTrue(result.passed, f"Rejections: {result.rejections}")

    def test_intent_id_mismatch(self):
        cert = _build_valid_cert()
        result = self.verifier.verify(
            cert=cert,
            order_intent_id="INTENT-999",
            intent_hash="abc123hash",
            symbol="NVDA", side="BUY", quantity=500,
        )
        self.assertFalse(result.passed)

    def test_intent_hash_mismatch(self):
        cert = _build_valid_cert()
        result = self.verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="tampered_hash",
            symbol="NVDA", side="BUY", quantity=500,
        )
        self.assertFalse(result.passed)

    def test_symbol_mismatch(self):
        cert = _build_valid_cert()
        result = self.verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="abc123hash",
            symbol="AAPL", side="BUY", quantity=500,
        )
        self.assertFalse(result.passed)

    def test_side_mismatch(self):
        cert = _build_valid_cert()
        result = self.verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="abc123hash",
            symbol="NVDA", side="SELL", quantity=500,
        )
        self.assertFalse(result.passed)

    def test_quantity_exceeds_scope(self):
        cert = _build_valid_cert()
        result = self.verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="abc123hash",
            symbol="NVDA", side="BUY", quantity=1500,
        )
        self.assertFalse(result.passed)

    def test_notional_exceeds_scope(self):
        cert = _build_valid_cert()
        result = self.verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="abc123hash",
            symbol="NVDA", side="BUY",
            quantity=500, notional=250000,
        )
        self.assertFalse(result.passed)

    def test_venue_mismatch(self):
        cert = _build_valid_cert()
        result = self.verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="abc123hash",
            symbol="NVDA", side="BUY", quantity=500,
            venue="NYSE",
        )
        self.assertFalse(result.passed)

    def test_governance_frozen_blocks(self):
        cert = _build_valid_cert()
        result = self.verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="abc123hash",
            symbol="NVDA", side="BUY", quantity=500,
            current_governance_state="FROZEN",
        )
        self.assertFalse(result.passed)

    def test_expired_certificate_rejected(self):
        cert = _build_valid_cert()
        cert.expire()
        result = self.verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="abc123hash",
            symbol="NVDA", side="BUY", quantity=500,
        )
        self.assertFalse(result.passed)


if __name__ == "__main__":
    unittest.main()
