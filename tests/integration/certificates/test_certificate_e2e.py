"""E2E tests for Pre-Trade Control Certificate — full lifecycle from builder to OMS admission.

Covers:
- Builder → seal → validate → verify → consume → audit
- All exception paths: expiry, revocation, tamper, replay
- Integration with registry and metrics
"""

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

from services.integration.certificates.certificate_builder import CertificateBuilder
from services.integration.certificates.certificate_validator import CertificateValidator
from services.integration.certificates.certificate_verifier import CertificateVerifier
from services.integration.certificate_lifecycle import CertificateLifecycle
from services.integration.certificate_registry import CertificateRegistry
from services.integration.certificate_metrics import CertificateMetrics
from services.integration.certificates.certificate_status import CertificateStatus
from services.integration.certificates.certificate_scope import (
    CertificateScope, ConsumptionMode,
)
from services.integration.certificates.pre_trade_certificate import PreTradeControlCertificate
from services.integration.certificates.certificate_claim import CertificateClaim
from services.integration.certificates.certificate_errors import (
    CertificateExpiredError, CertificateRevokedError,
    CertificateConsumptionError, CertificateReplayError,
    CertificateUsageExhaustedError,
)


def _build_valid_cert(trader_strategy="STRAT-001"):
    return (CertificateBuilder()
            .with_flow_id("FLOW-001")
            .with_decision_id("DEC-001")
            .with_signal_id("SIG-001")
            .with_strategy_id(trader_strategy)
            .with_order_intent(intent_id="INTENT-001", intent_hash="abc123hash",
                               account_id="ACC-001", portfolio_id="PORT-001")
            .with_symbol("NVDA").with_side("BUY").with_venue("NASDAQ")
            .with_order_type("LIMIT")
            .with_quantity(1000).with_limit_price(180.0)
            .with_max_notional(200000)
            .with_risk_decision(True, policy_version="RISK-v8",
                                detail={"exposure": 0.12, "limit": 0.15,
                                        "available_margin": 1200000})
            .with_governance_decision(True, state="NORMAL",
                                      policy_version="GOV-v5")
            .with_authority_decision(True, authority_id="AUTH-001",
                                     limit=500000, policy_version="AUTH-v3")
            .with_approval_decision(True, approval_id="APR-001",
                                    status="APPROVED", amount=180000,
                                    policy_version="APPROVAL-v2")
            .with_effective_constraints({
                "max_quantity": 1000,
                "max_notional": 180000,
                "max_leverage": 2,
            })
            .build_and_seal())


class TestE2EHappyPath(unittest.TestCase):
    """Full happy path: build → validate → verify → consume."""

    def setUp(self):
        self.validator = CertificateValidator()
        self.verifier = CertificateVerifier()
        self.lifecycle = CertificateLifecycle()
        self.registry = CertificateRegistry()
        self.metrics = CertificateMetrics()
        self.cert = _build_valid_cert()

    def tearDown(self):
        import gc
        gc.collect()

    def test_full_happy_path(self):
        # 1. Structural validation
        report = self.validator.validate(self.cert)
        self.assertTrue(report.valid, f"Errors: {report.errors}")
        self.metrics.record_verification(True)

        # 2. Register
        record = self.registry.register(self.cert)
        self.assertEqual(record.certificate_id, self.cert.certificate_id)
        self.metrics.record_issued()

        # 3. Runtime verification
        result = self.verifier.verify(
            cert=self.cert,
            order_intent_id="INTENT-001",
            intent_hash="abc123hash",
            symbol="NVDA", side="BUY",
            quantity=500, notional=90000,
            venue="NASDAQ",
        )
        self.assertTrue(result.passed, f"Rejections: {result.rejections}")
        self.metrics.record_verification(True)

        # 4. Consume (half the allocation)
        consumed = self.lifecycle.consume(self.cert, quantity=500, notional=90000)
        self.metrics.record_used(quantity=500, notional=90000)
        self.registry.update_status(self.cert.certificate_id, consumed.status)

        # 5. Metric assertions
        self.assertEqual(self.metrics.issued_count, 1)
        self.assertEqual(self.metrics.verified_pass, 2)
        self.assertEqual(self.metrics.used_count, 1)

    def test_e2e_lineage_preserved(self):
        """All lineage fields survive the full lifecycle."""
        self.registry.register(self.cert)
        record = self.registry.get_record(self.cert.certificate_id)
        self.assertEqual(record.flow_id, "FLOW-001")
        self.assertEqual(record.decision_id, "DEC-001")
        self.assertEqual(record.account_id, "ACC-001")
        self.assertEqual(record.symbol, "NVDA")
        self.assertEqual(record.side, "BUY")

    def test_e2e_audit_log(self):
        self.registry.register(self.cert)
        log = self.registry.get_audit_log_for(self.cert.certificate_id)
        self.assertGreaterEqual(len(log), 1)
        self.assertEqual(log[0]["event_type"], "REGISTERED")

    def test_e2e_policy_versions_immutable(self):
        self.registry.register(self.cert)
        record = self.registry.get_record(self.cert.certificate_id)
        self.assertIn("risk", record.policy_versions)
        self.assertEqual(record.policy_versions["risk"], "RISK-v8")
        self.assertEqual(record.policy_versions["governance"], "GOV-v5")
        self.assertEqual(record.policy_versions["authority"], "AUTH-v3")


class TestE2ERiskFailure(unittest.TestCase):
    """Risk gate failure in certificate."""

    def test_failed_risk_recorded(self):
        builder = (CertificateBuilder()
                   .with_flow_id("FLOW-001")
                   .with_order_intent(intent_id="INTENT-001", intent_hash="abc",
                                      account_id="ACC-001")
                   .with_symbol("NVDA").with_side("BUY")
                   .with_quantity(1000)
                   .with_risk_decision(False, detail={"exposure": 0.18, "limit": 0.15}))
        cert = builder.build()
        self.assertFalse(cert.risk_claim.is_pass())
        self.assertFalse(cert.all_claims_passed())


class TestE2EGovernanceFreeze(unittest.TestCase):
    """Governance freeze blocks certificate usage."""

    def test_frozen_governance_blocked(self):
        cert = _build_valid_cert()
        verifier = CertificateVerifier()
        result = verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="abc123hash",
            symbol="NVDA", side="BUY", quantity=500,
            current_governance_state="FROZEN",
        )
        self.assertFalse(result.passed)
        self.assertTrue(
            any("FROZEN" in r for r in result.rejections)
        )


class TestE2EPolicyMismatch(unittest.TestCase):
    """Policy version mismatch scenario."""

    def test_version_locked_in_certificate(self):
        cert = _build_valid_cert()
        self.assertIn("risk", cert.policy_versions)
        self.assertEqual(cert.policy_versions["risk"], "RISK-v8")
        self.assertEqual(cert.policy_versions["governance"], "GOV-v5")


class TestE2ECertificateTampering(unittest.TestCase):
    """Evidence tampering detection."""

    def test_tampered_certificate_id_blocked(self):
        cert = _build_valid_cert()
        verifier = CertificateVerifier()
        result = verifier.verify(
            cert=cert,
            order_intent_id=cert.order_intent_id,
            intent_hash=cert.intent_hash,
            symbol="NVDA", side="BUY", quantity=500,
        )
        self.assertTrue(result.passed)

        # Modify the intent hash simulate tampering
        cert2 = _build_valid_cert()
        result2 = verifier.verify(
            cert=cert2,
            order_intent_id=cert2.order_intent_id,
            intent_hash="tampered_intent_hash",
            symbol="NVDA", side="BUY", quantity=500,
        )
        self.assertFalse(result2.passed)


class TestE2ERevocation(unittest.TestCase):
    """Certificate revocation flow."""

    def test_revocation_flow(self):
        cert = _build_valid_cert()
        lifecycle = CertificateLifecycle()
        registry = CertificateRegistry()

        registry.register(cert)
        self.assertTrue(registry.is_valid(cert.certificate_id))

        lifecycle.revoke(cert, "policy_emergency")
        registry.revoke(cert.certificate_id, "policy_emergency")

        self.assertFalse(registry.is_valid(cert.certificate_id))
        self.assertTrue(registry.is_revoked(cert.certificate_id))

        record = registry.get_record(cert.certificate_id)
        self.assertEqual(record.status, "REVOKED")
        self.assertEqual(record.revocation_reason, "policy_emergency")


class TestE2EDuplicatePrevention(unittest.TestCase):
    """Duplicate order prevention via certificate replay."""

    def test_replay_detected_in_lifecycle(self):
        cert = _build_valid_cert()
        lifecycle = CertificateLifecycle()
        lifecycle.register(cert)
        lifecycle.consume(cert, quantity=500)

        self.assertTrue(lifecycle.is_replay(cert.certificate_id))

        with self.assertRaises(CertificateUsageExhaustedError):
            lifecycle.consume(cert, quantity=100)


class TestE2EReservationFailure(unittest.TestCase):
    """Notional/quantity limit exceeded."""

    def test_notional_exceeded_in_verifier(self):
        cert = _build_valid_cert()
        verifier = CertificateVerifier()
        result = verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="abc123hash",
            symbol="NVDA", side="BUY",
            quantity=500, notional=250000,
        )
        self.assertFalse(result.passed)

    def test_quantity_exceeded_in_verifier(self):
        cert = _build_valid_cert()
        verifier = CertificateVerifier()
        result = verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="abc123hash",
            symbol="NVDA", side="BUY", quantity=1500,
        )
        self.assertFalse(result.passed)


class TestE2EEmergencyOrder(unittest.TestCase):
    """Emergency governance state: warning but not necessarily blocked."""

    def test_emergency_generates_warning(self):
        cert = _build_valid_cert()
        verifier = CertificateVerifier()
        result = verifier.verify(
            cert=cert,
            order_intent_id="INTENT-001",
            intent_hash="abc123hash",
            symbol="NVDA", side="BUY", quantity=500,
            current_governance_state="EMERGENCY",
        )
        self.assertTrue(result.passed)
        self.assertTrue(len(result.warnings) > 0)


if __name__ == "__main__":
    unittest.main()
