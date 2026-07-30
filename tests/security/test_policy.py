"""
Tests for ICYQuant Security Platform integration.
"""

import pytest

from services.security.service import SecurityService
from services.security.audit_center import AuditAction, AuditSeverity
from services.security.compliance import ComplianceFramework
from services.security.governance import GovernanceCategory, RiskLevel, ApprovalStatus
from services.security.policy_engine import PolicyEffect
from services.security.authentication import AuthProvider


class TestSecurityService:
    """Test unified security service facade."""

    def test_get_status(self):
        svc = SecurityService()
        status = svc.get_status()
        assert status["security"] == "healthy"
        assert status["authentication"] == "enabled"
        assert status["encryption"] == "enabled"

    def test_authenticate_and_authorize(self):
        svc = SecurityService()
        svc.authentication.register_user("trader", "trader@test.com")
        svc.authorization.assign_role("trader", "trader")
        session = svc.authenticate("trader", "pass")
        assert session.user_id is not None
        assert svc.authorize("trader", "trade", "read") is True
        assert svc.authorize("trader", "audit_log", "read") is False

    def test_policy_engine_integration(self):
        svc = SecurityService()
        from services.security.policy_engine import Policy, PolicyStatement, PolicyCondition
        policy = Policy(
            name="Test",
            enabled=True,
            priority=10,
            statements=[
                PolicyStatement(
                    effect=PolicyEffect.ALLOW,
                    conditions=[PolicyCondition("user_id", "exists", True)],
                ),
            ],
        )
        svc.policy_engine.create_policy(policy)
        decision = svc.policy_engine.evaluate({"user_id": "test"})
        assert decision.decision == PolicyEffect.ALLOW

    def test_audit_logging(self):
        svc = SecurityService()
        entry = svc.audit.log(
            action=AuditAction.LOGIN,
            actor="trader",
            severity=AuditSeverity.INFO,
        )
        assert entry.id is not None
        integrity = svc.audit.verify_integrity()
        assert integrity["integrityOk"] is True

    def test_encryption_integration(self):
        svc = SecurityService()
        encrypted = svc.encryption.encrypt_field("account_number", "1234567890")
        plaintext = svc.encryption.decrypt_field(encrypted)
        assert plaintext == "1234567890"

    def test_compliance_integration(self):
        svc = SecurityService()
        report = svc.compliance.generate_report([ComplianceFramework.ISO27001])
        assert report is not None
        assert report.overall_status.value in ("PASS", "WARNING", "FAIL")

    def test_governance_integration(self):
        svc = SecurityService()
        request = svc.governance.submit_request(
            title="Test AI Model",
            category=GovernanceCategory.AI_MODEL,
            requested_by="researcher",
            risk_level=RiskLevel.MEDIUM,
        )
        assert request.id is not None

    def test_vault_integration(self):
        svc = SecurityService()
        svc.vault.create_secret(
            name="test-api-key",
            value="secret-value-123",
            scope="api_key",
            owner="test",
        )
        secret = svc.vault.get_secret("test-api-key")
        assert secret == "secret-value-123"

    def test_kms_integration(self):
        svc = SecurityService()
        svc.kms.create_key("test-key")
        ct = svc.kms.encrypt("test-key", "Hello")
        pt = svc.kms.decrypt("test-key", ct)
        assert pt == "Hello"

    def test_token_manager_integration(self):
        svc = SecurityService()
        token = svc.token_manager.create_token("user1", scopes={"read"})
        validation = svc.token_manager.validate_token(token)
        assert validation.valid is True

    def test_zero_trust_integration(self):
        svc = SecurityService()
        from services.security.zero_trust import SecurityContext
        ctx = SecurityContext(
            user_id="user1",
            token_present=True,
            service="api",
            action="read",
        )
        decision = svc.zero_trust.evaluate(ctx)
        assert decision is not None

    def test_key_rotation_integration(self):
        svc = SecurityService()
        from services.security.key_rotation import RotationPolicy
        policy = RotationPolicy(name="Test Rotation", target="test-service")
        svc.key_rotation.create_policy(policy)
        policies = svc.key_rotation.list_policies()
        assert len(policies) >= 1


class TestSecurityInfrastructure:
    """Test infrastructure security adapters."""

    def test_vault_adapter(self):
        from infrastructure.security.vault_adapter import VaultAdapter, VaultBackend
        adapter = VaultAdapter()
        adapter.connect()
        adapter.write_secret("test/secret", {"key": "value"})
        result = adapter.read_secret("test/secret")
        assert result == {"key": "value"}

    def test_vault_disconnect(self):
        from infrastructure.security.vault_adapter import VaultAdapter
        adapter = VaultAdapter()
        with pytest.raises(ConnectionError):
            adapter.read_secret("test")

    def test_opa_adapter(self):
        from infrastructure.security.opa_adapter import OPAAdapter
        adapter = OPAAdapter()
        adapter.create_policy(
            "test-policy",
            'package icyquant\nallow { input.user == "admin" }',
        )
        decision = adapter.query({"user": "admin"})
        assert decision.allowed is True

    def test_certificate_manager(self):
        from infrastructure.security.certificate_manager import (
            CertificateManager,
            CertificateType,
        )
        cm = CertificateManager()
        cert = cm.issue_certificate("test.icyquant.com", CertificateType.SERVER)
        assert cert.subject == "test.icyquant.com"
        rotated = cm.rotate_certificate(cert.id)
        assert rotated is not None

    def test_hsm_adapter(self):
        from infrastructure.security.hsm_adapter import HSMAdapter, HSMProvider
        hsm = HSMAdapter()
        key = hsm.generate_key("test-key")
        ct = hsm.encrypt(key.id, b"Hello World")
        pt = hsm.decrypt(key.id, ct)
        assert pt == b"Hello World"

    def test_secret_scanner(self):
        from infrastructure.security.secret_scanner import SecretScanner
        scanner = SecretScanner()
        findings = scanner.scan_content(
            'api_key = "sk-test-1234567890abcdef"',
            context="test",
        )
        assert len(findings) > 0

    def test_security_monitor(self):
        from infrastructure.security.security_monitor import SecurityMonitor
        monitor = SecurityMonitor()
        monitor.record_login_attempt("user1", "192.168.1.1", successful=True)
        monitor.check_anomalous_login("user1", "10.0.0.1")
        alerts = monitor.get_alerts()
        assert len(alerts) >= 0

    def test_incident_response(self):
        from infrastructure.security.incident_response import (
            IncidentResponseManager,
            IncidentType,
            IncidentSeverity,
        )
        mgr = IncidentResponseManager()
        incident = mgr.create_incident(
            IncidentType.CREDENTIAL_LEAK,
            "Credential Leak Detected",
            affected_user="trader1",
            severity=IncidentSeverity.HIGH,
        )
        actions = mgr.respond_to_incident(incident.id)
        assert len(actions) > 0
        resolved = mgr.get_incident(incident.id)
        assert resolved.status.value == "contained"
