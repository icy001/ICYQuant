"""Tests for certificate expiry behaviour and lifecycle."""

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

from services.integration.certificates.pre_trade_certificate import PreTradeControlCertificate
from services.integration.certificates.certificate_status import CertificateStatus
from services.integration.certificate_lifecycle import CertificateLifecycle
from services.integration.certificates.certificate_scope import CertificateScope, ConsumptionMode
from services.integration.certificates.certificate_errors import CertificateExpiredError


class TestCertificateTTL(unittest.TestCase):

    def test_not_expired_within_window(self):
        cert = PreTradeControlCertificate(expires_at=time.time() + 3600)
        self.assertFalse(cert.is_expired)
        self.assertTrue(cert.is_active)

    def test_expired_past_window(self):
        cert = PreTradeControlCertificate(expires_at=time.time() - 1)
        self.assertTrue(cert.is_expired)
        self.assertFalse(cert.is_active)

    def test_no_expiry_is_active(self):
        cert = PreTradeControlCertificate()
        self.assertFalse(cert.is_expired)


class TestLifecycleExpiry(unittest.TestCase):

    def setUp(self):
        self.lifecycle = CertificateLifecycle()

    def test_expire_transitions(self):
        cert = PreTradeControlCertificate(flow_id="FLOW-001")
        cert.activate()
        self.lifecycle.register(cert)
        cert = self.lifecycle.expire(cert)
        self.assertEqual(cert.status, CertificateStatus.EXPIRED)
        self.assertIsNone(self.lifecycle.get_certificate(cert.certificate_id))

    def test_expired_cannot_consume(self):
        cert = PreTradeControlCertificate(
            flow_id="FLOW-001",
            scope=CertificateScope(max_quantity=1000),
            expires_at=time.time() - 1,
        )
        with self.assertRaises(CertificateExpiredError):
            self.lifecycle.consume(cert, quantity=100)

    def test_pending_expiry_check(self):
        cert = PreTradeControlCertificate(
            flow_id="FLOW-001",
            scope=CertificateScope(max_quantity=1000),
            expires_at=time.time() - 3600,
        )
        cert.activate()
        self.lifecycle.register(cert)
        expired = self.lifecycle.pending_expiry_check()
        self.assertIn(cert.certificate_id, expired)


class TestScopeExpiry(unittest.TestCase):

    def test_scope_tracks_expiry(self):
        scope = CertificateScope(expires_at=time.time() + 3600)
        self.assertTrue(scope.is_active())

    def test_scope_past_expiry(self):
        scope = CertificateScope(expires_at=time.time() - 1)
        self.assertFalse(scope.is_active())


if __name__ == "__main__":
    unittest.main()
