"""Tests for PreTradeControlCertificate — core certificate lifecycle."""

from __future__ import annotations

import sys
import os
import types
import importlib.util
import unittest
import time

_ws = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_int_dir = os.path.join(_ws, "services", "integration")
_cert_dir = os.path.join(_int_dir, "certificates")

if "services" not in sys.modules:
    _svc = types.ModuleType("services")
    _svc.__path__ = [os.path.join(_ws, "services")]
    sys.modules["services"] = _svc
if "services.integration" not in sys.modules:
    _mod = types.ModuleType("services.integration")
    _mod.__path__ = [_int_dir]
    sys.modules["services.integration"] = _mod
if "services.integration.certificates" not in sys.modules:
    _pkg = types.ModuleType("services.integration.certificates")
    _pkg.__path__ = [_cert_dir]
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

for _name in [
    "certificate_lifecycle", "certificate_registry", "certificate_metrics",
]:
    _fp = os.path.join(_int_dir, f"{_name}.py")
    if not os.path.exists(_fp): continue
    _mod_name = f"services.integration.{_name}"
    if _mod_name in sys.modules: continue
    _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
    _m = importlib.util.module_from_spec(_spec)
    sys.modules[_mod_name] = _m
    _spec.loader.exec_module(_m)

from services.integration.certificates.pre_trade_certificate import (
    PreTradeControlCertificate, create_empty_certificate,
)
from services.integration.certificates.certificate_status import CertificateStatus
from services.integration.certificates.certificate_scope import (
    CertificateScope, ConsumptionMode,
)
from services.integration.certificates.certificate_claim import CertificateClaim
from services.integration.certificates.certificate_evidence import CertificateEvidence


class TestPreTradeCertificateCreation(unittest.TestCase):

    def test_empty_certificate(self):
        cert = create_empty_certificate()
        self.assertTrue(cert.certificate_id.startswith("CERT-"))
        self.assertEqual(cert.status, CertificateStatus.ISSUED)

    def test_certificate_has_lineage_fields(self):
        cert = PreTradeControlCertificate(
            flow_id="FLOW-001",
            decision_id="DEC-001",
            strategy_id="STRAT-001",
            account_id="ACC-001",
            order_intent_id="INTENT-001",
        )
        self.assertEqual(cert.flow_id, "FLOW-001")
        self.assertEqual(cert.decision_id, "DEC-001")

    def test_certificate_with_claims(self):
        cert = PreTradeControlCertificate(
            flow_id="FLOW-001",
            risk_claim=CertificateClaim.risk_claim(True, policy_version="RISK-v8"),
            governance_claim=CertificateClaim.governance_claim(True, state="NORMAL"),
            authority_claim=CertificateClaim.authority_claim(True, limit=10000000),
            approval_claim=CertificateClaim.approval_claim(True, status="APPROVED"),
        )
        self.assertIsNotNone(cert.risk_claim)
        self.assertTrue(cert.risk_claim.is_pass())


class TestPreTradeCertificateLifecycle(unittest.TestCase):
    """Certificate status transitions."""

    def setUp(self):
        self.cert = PreTradeControlCertificate(flow_id="FLOW-001")

    def tearDown(self):
        import gc
        gc.collect()

    def test_issued_to_valid(self):
        self.cert.activate()
        self.assertEqual(self.cert.status, CertificateStatus.VALID)

    def test_valid_to_used(self):
        self.cert.activate()
        self.cert.mark_used()
        self.assertEqual(self.cert.status, CertificateStatus.USED)
        self.assertIsNotNone(self.cert.used_at)

    def test_valid_to_revoked(self):
        self.cert.activate()
        self.cert.revoke("governance_freeze")
        self.assertEqual(self.cert.status, CertificateStatus.REVOKED)
        self.assertEqual(self.cert.revocation_reason, "governance_freeze")

    def test_valid_to_expired(self):
        self.cert.activate()
        self.cert.expire()
        self.assertEqual(self.cert.status, CertificateStatus.EXPIRED)

    def test_invalid_transition_raises(self):
        self.cert.activate()
        self.cert.mark_used()
        with self.assertRaises(ValueError):
            self.cert.activate()


class TestPreTradeCertificateActive(unittest.TestCase):
    """Certificate active state checks."""

    def test_issued_is_active(self):
        cert = PreTradeControlCertificate()
        self.assertTrue(cert.is_active)

    def test_valid_is_active(self):
        cert = PreTradeControlCertificate()
        cert.activate()
        self.assertTrue(cert.is_active)

    def test_used_not_active(self):
        cert = PreTradeControlCertificate()
        cert.activate()
        cert.mark_used()
        self.assertFalse(cert.is_active)

    def test_revoked_not_active(self):
        cert = PreTradeControlCertificate()
        cert.activate()
        cert.revoke("test")
        self.assertFalse(cert.is_active)

    def test_expired_not_active(self):
        cert = PreTradeControlCertificate()
        cert.activate()
        cert.expire()
        self.assertFalse(cert.is_active)

    def test_expired_by_ttl(self):
        cert = PreTradeControlCertificate(expires_at=time.time() - 1)
        self.assertTrue(cert.is_expired)
        self.assertFalse(cert.is_active)


class TestSealAndFingerprint(unittest.TestCase):
    """Certificate sealing (fingerprint + signature)."""

    def setUp(self):
        self.cert = PreTradeControlCertificate(
            flow_id="FLOW-001",
            decision_id="DEC-001",
            order_intent_id="INTENT-001",
            account_id="ACC-001",
            intent_hash="abc123",
            scope=CertificateScope.for_order(
                account_id="ACC-001", symbol="NVDA", side="BUY",
                max_quantity=1000,
            ),
            risk_claim=CertificateClaim.risk_claim(True),
            governance_claim=CertificateClaim.governance_claim(True),
            authority_claim=CertificateClaim.authority_claim(True),
            approval_claim=CertificateClaim.approval_claim(True),
            evidence=[CertificateEvidence.risk_evidence(portfolio_exposure=0.12)],
            policy_versions={"risk": "RISK-v8"},
        )

    def tearDown(self):
        import gc
        gc.collect()

    def test_seal_produces_fingerprint(self):
        self.cert.seal()
        self.assertIsNotNone(self.cert.fingerprint)
        self.assertIsNotNone(self.cert.signature)
        self.assertEqual(self.cert.status, CertificateStatus.VALID)

    def test_fingerprint_compute_manual(self):
        fp = self.cert.compute_fingerprint()
        self.assertTrue(len(fp.fingerprint_hash) > 0)
        self.assertEqual(fp, self.cert.fingerprint)

    def test_signature_compute_manual(self):
        self.cert.compute_fingerprint()
        sig = self.cert.compute_signature()
        self.assertTrue(len(sig.hash_value) > 0)

    def test_signature_verification_passes(self):
        self.cert.seal()
        self.assertTrue(
            self.cert.signature.verify(
                certificate_id=self.cert.certificate_id,
                flow_id=self.cert.flow_id,
                order_intent_id=self.cert.order_intent_id,
                intent_hash=self.cert.intent_hash,
                scope_info=self.cert.scope.to_dict(),
                constraints_info=self.cert.effective_constraints,
                policy_versions=self.cert.policy_versions,
                claims_list=self.cert.claims_as_dict_list(),
                evidence_list=self.cert.evidence_as_dict_list(),
            )
        )

    def test_signature_verification_fails_on_tamper(self):
        self.cert.seal()
        self.assertFalse(
            self.cert.signature.verify(
                certificate_id="TAMPERED-ID",
                flow_id=self.cert.flow_id,
                order_intent_id=self.cert.order_intent_id,
                intent_hash=self.cert.intent_hash,
                scope_info=self.cert.scope.to_dict(),
                constraints_info=self.cert.effective_constraints,
                policy_versions=self.cert.policy_versions,
                claims_list=self.cert.claims_as_dict_list(),
                evidence_list=self.cert.evidence_as_dict_list(),
            )
        )


class TestAllClaimsPassed(unittest.TestCase):

    def test_all_pass(self):
        cert = PreTradeControlCertificate(
            risk_claim=CertificateClaim.risk_claim(True),
            governance_claim=CertificateClaim.governance_claim(True),
            authority_claim=CertificateClaim.authority_claim(True),
            approval_claim=CertificateClaim.approval_claim(True),
        )
        self.assertTrue(cert.all_claims_passed())

    def test_one_fails(self):
        cert = PreTradeControlCertificate(
            risk_claim=CertificateClaim.risk_claim(True),
            governance_claim=CertificateClaim.governance_claim(False),
            authority_claim=CertificateClaim.authority_claim(True),
            approval_claim=CertificateClaim.approval_claim(True),
        )
        self.assertFalse(cert.all_claims_passed())


class TestSerialization(unittest.TestCase):

    def test_to_dict(self):
        cert = PreTradeControlCertificate(
            flow_id="FLOW-001",
            decision_id="DEC-001",
            account_id="ACC-001",
        )
        d = cert.to_dict()
        self.assertEqual(d["flow_id"], "FLOW-001")
        self.assertEqual(d["status"], "ISSUED")


if __name__ == "__main__":
    unittest.main()
