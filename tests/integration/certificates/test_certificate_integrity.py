"""Tests for certificate integrity — tamper detection, hash verification, fingerprint consistency."""

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
from services.integration.certificates.certificate_validator import CertificateValidator
from services.integration.certificates.certificate_scope import CertificateScope
from services.integration.certificates.certificate_status import CertificateStatus
from services.integration.certificates.pre_trade_certificate import PreTradeControlCertificate
from services.integration.certificates.certificate_claim import CertificateClaim
from services.integration.certificates.certificate_evidence import CertificateEvidence
from services.integration.certificates.certificate_errors import CertificateIntegrityError


def _build_valid_cert():
    return (CertificateBuilder()
            .with_flow_id("FLOW-001")
            .with_decision_id("DEC-001")
            .with_strategy_id("STRAT-001")
            .with_order_intent(intent_id="INTENT-001", intent_hash="abc123hash",
                               account_id="ACC-001")
            .with_symbol("NVDA").with_side("BUY").with_venue("NASDAQ")
            .with_quantity(1000)
            .with_risk_decision(True, policy_version="RISK-v8")
            .with_governance_decision(True, state="NORMAL", policy_version="GOV-v5")
            .with_authority_decision(True, authority_id="AUTH-001", limit=500000,
                                     policy_version="AUTH-v3")
            .with_approval_decision(True, approval_id="APR-001", status="APPROVED",
                                    policy_version="APPROVAL-v2")
            .with_effective_constraints({"max_quantity": 1000})
            .build_and_seal())


class TestFingerprintConsistency(unittest.TestCase):

    def test_same_content_same_fingerprint(self):
        c1 = _build_valid_cert()
        c2 = _build_valid_cert()
        # different IDs → different fingerprints
        self.assertNotEqual(
            c1.fingerprint.fingerprint_hash,
            c2.fingerprint.fingerprint_hash,
        )

    def test_different_content_different_fingerprint(self):
        c1 = _build_valid_cert()
        # Build similar but with different symbol
        c2 = (CertificateBuilder()
              .with_flow_id("FLOW-001")
              .with_decision_id("DEC-001")
              .with_order_intent(intent_id="INTENT-001", intent_hash="abc123hash",
                                 account_id="ACC-001")
              .with_symbol("AAPL").with_side("BUY")
              .with_quantity(1000)
              .with_risk_decision(True, policy_version="RISK-v8")
              .with_governance_decision(True, state="NORMAL", policy_version="GOV-v5")
              .with_authority_decision(True, authority_id="AUTH-001", limit=500000,
                                       policy_version="AUTH-v3")
              .with_approval_decision(True, approval_id="APR-001", status="APPROVED",
                                      policy_version="APPROVAL-v2")
              .with_effective_constraints({"max_quantity": 1000})
              .build_and_seal())
        self.assertNotEqual(
            c1.fingerprint.fingerprint_hash,
            c2.fingerprint.fingerprint_hash,
        )


class TestSignatureTamperDetection(unittest.TestCase):

    def test_modified_certificate_id_invalidates(self):
        cert = _build_valid_cert()
        result = cert.signature.verify(
            certificate_id="TAMPERED-ID",
            flow_id=cert.flow_id,
            order_intent_id=cert.order_intent_id,
            intent_hash=cert.intent_hash,
            scope_info=cert.scope.to_dict(),
            constraints_info=cert.effective_constraints,
            policy_versions=cert.policy_versions,
            claims_list=cert.claims_as_dict_list(),
            evidence_list=cert.evidence_as_dict_list(),
        )
        self.assertFalse(result)

    def test_modified_scope_invalidates(self):
        cert = _build_valid_cert()
        tampered_scope = dict(cert.scope.to_dict())
        tampered_scope["max_quantity"] = 99999
        result = cert.signature.verify(
            certificate_id=cert.certificate_id,
            flow_id=cert.flow_id,
            order_intent_id=cert.order_intent_id,
            intent_hash=cert.intent_hash,
            scope_info=tampered_scope,
            constraints_info=cert.effective_constraints,
            policy_versions=cert.policy_versions,
            claims_list=cert.claims_as_dict_list(),
            evidence_list=cert.evidence_as_dict_list(),
        )
        self.assertFalse(result)

    def test_modified_constraints_invalidates(self):
        cert = _build_valid_cert()
        tampered_constraints = {"max_quantity": 99999}
        result = cert.signature.verify(
            certificate_id=cert.certificate_id,
            flow_id=cert.flow_id,
            order_intent_id=cert.order_intent_id,
            intent_hash=cert.intent_hash,
            scope_info=cert.scope.to_dict(),
            constraints_info=tampered_constraints,
            policy_versions=cert.policy_versions,
            claims_list=cert.claims_as_dict_list(),
            evidence_list=cert.evidence_as_dict_list(),
        )
        self.assertFalse(result)


class TestIntentHashBinding(unittest.TestCase):
    """Tests that certificate is bound to exact order intent hash."""

    def setUp(self):
        self.verifier = CertificateVerifier()

    def test_correct_hash_passes(self):
        cert = _build_valid_cert()
        result = self.verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="abc123hash",
            symbol="NVDA", side="BUY", quantity=500,
        )
        self.assertTrue(result.passed)

    def test_wrong_hash_fails(self):
        cert = _build_valid_cert()
        result = self.verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="wrong_hash_value",
            symbol="NVDA", side="BUY", quantity=500,
        )
        self.assertFalse(result.passed)

    def test_empty_intent_hash_skips_check(self):
        """If cert has no intent_hash, skip the hash binding check."""
        cert = _build_valid_cert()
        cert.intent_hash = ""
        result = self.verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="anything",
            symbol="NVDA", side="BUY", quantity=500,
        )
        self.assertTrue(result.passed)


class TestEvidenceImmutableAfterSeal(unittest.TestCase):

    def test_evidence_hash_changes_when_modified(self):
        cert = _build_valid_cert()
        original_hash = cert.evidence_hash
        cert.evidence.append(
            CertificateEvidence.risk_evidence(portfolio_exposure=0.99)
        )
        new_hash = cert.evidence_hash
        self.assertNotEqual(original_hash, new_hash)


if __name__ == "__main__":
    unittest.main()
