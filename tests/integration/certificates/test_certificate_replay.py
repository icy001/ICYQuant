"""Tests for certificate replay protection and one-time usage."""

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
from services.integration.certificates.certificate_scope import CertificateScope, ConsumptionMode
from services.integration.certificate_lifecycle import CertificateLifecycle
from services.integration.certificates.certificate_verifier import CertificateVerifier
from services.integration.certificates.certificate_errors import (
    CertificateReplayError, CertificateUsageExhaustedError,
    CertificateConsumptionError, CertificateRevokedError,
)
from services.integration.certificates.pre_trade_certificate import PreTradeControlCertificate


def _build_one_time_cert():
    return (CertificateBuilder()
            .with_flow_id("FLOW-001")
            .with_decision_id("DEC-001")
            .with_order_intent(intent_id="INTENT-001", intent_hash="abc",
                               account_id="ACC-001")
            .with_symbol("NVDA").with_side("BUY")
            .with_quantity(1000)
            .with_risk_decision(True, policy_version="RISK-v8")
            .with_governance_decision(True, state="NORMAL")
            .with_authority_decision(True, authority_id="AUTH-001", limit=500000)
            .with_approval_decision(True, approval_id="APR-001", status="APPROVED")
            .build_and_seal())


class TestOneTimeCertificate(unittest.TestCase):

    def setUp(self):
        self.lifecycle = CertificateLifecycle()
        self.verifier = CertificateVerifier()

    def test_one_time_single_use(self):
        cert = _build_one_time_cert()
        self.assertEqual(cert.scope.consumption_mode, ConsumptionMode.ONE_TIME)
        # cert is already VALID from build_and_seal()
        self.lifecycle.register(cert)
        self.assertEqual(cert.status, CertificateStatus.VALID)

    def test_one_time_marked_used(self):
        cert = _build_one_time_cert()
        self.lifecycle.register(cert)
        self.lifecycle.consume(cert, quantity=500)
        self.assertEqual(cert.status, CertificateStatus.USED)

    def test_used_certificate_cannot_be_reused(self):
        cert = _build_one_time_cert()
        self.lifecycle.register(cert)
        self.lifecycle.consume(cert, quantity=500)
        with self.assertRaises(CertificateUsageExhaustedError):
            self.lifecycle.consume(cert, quantity=100)

    def test_replay_detected_by_verifier(self):
        cert = _build_one_time_cert()
        self.lifecycle.register(cert)
        self.lifecycle.consume(cert, quantity=500)

        result = self.verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="abc",
            symbol="NVDA", side="BUY", quantity=500,
        )
        self.assertFalse(result.passed)

    def test_lifecycle_tracks_used_ids(self):
        cert = _build_one_time_cert()
        self.lifecycle.register(cert)
        self.lifecycle.consume(cert, quantity=500)
        self.assertTrue(self.lifecycle.is_replay(cert.certificate_id))

    def test_unused_not_replay(self):
        cert = _build_one_time_cert()
        self.lifecycle.register(cert)
        self.assertFalse(self.lifecycle.is_replay(cert.certificate_id))


class TestQuantityCappedCertificate(unittest.TestCase):

    def setUp(self):
        self.lifecycle = CertificateLifecycle()

    def _build_quantity_capped(self, max_qty=1000):
        builder = (CertificateBuilder()
                   .with_flow_id("FLOW-001")
                   .with_decision_id("DEC-001")
                   .with_order_intent(intent_id="INTENT-001", intent_hash="abc",
                                      account_id="ACC-001")
                   .with_symbol("NVDA").with_side("BUY")
                   .with_quantity(max_qty)
                   .with_risk_decision(True).with_governance_decision(True)
                   .with_authority_decision(True).with_approval_decision(True))
        builder._scope_consumption_mode = ConsumptionMode.QUANTITY_CAPPED
        return builder.build_and_seal()

    def test_partial_consumption(self):
        cert = self._build_quantity_capped(1000)
        self.lifecycle.register(cert)
        self.lifecycle.consume(cert, quantity=400)
        self.assertEqual(cert.scope.quantity_consumed, 400)
        self.assertEqual(cert.status, CertificateStatus.VALID)

    def test_multiple_consumptions(self):
        cert = self._build_quantity_capped(1000)
        self.lifecycle.register(cert)
        self.lifecycle.consume(cert, quantity=400)
        self.lifecycle.consume(cert, quantity=500)
        self.assertEqual(cert.scope.quantity_consumed, 900)

    def test_exhausted_becomes_used(self):
        cert = self._build_quantity_capped(1000)
        self.lifecycle.register(cert)
        self.lifecycle.consume(cert, quantity=1000)
        self.assertEqual(cert.status, CertificateStatus.USED)

    def test_exceed_capped_raises(self):
        cert = self._build_quantity_capped(1000)
        self.lifecycle.register(cert)
        with self.assertRaises(CertificateConsumptionError):
            self.lifecycle.consume(cert, quantity=1500)


class TestRevokedCannotReplay(unittest.TestCase):

    def setUp(self):
        self.lifecycle = CertificateLifecycle()

    def test_revoked_certificate_blocked(self):
        cert = _build_one_time_cert()
        self.lifecycle.register(cert)
        self.lifecycle.revoke(cert, "governance_emergency")
        with self.assertRaises(CertificateRevokedError):
            self.lifecycle.consume(cert, quantity=100)


if __name__ == "__main__":
    unittest.main()
