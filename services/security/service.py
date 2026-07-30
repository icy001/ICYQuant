"""
ICYQuant Security Service - Main Facade

Unified security service facade providing a single entry point
for all security, compliance, and governance operations.
"""

from __future__ import annotations

from typing import Dict, Optional
from datetime import datetime
import logging

from services.security.authentication import (
    AuthenticationService,
    AuthProvider,
    TokenType,
)
from services.security.authorization import (
    AuthorizationService,
    Permission,
    ResourceType,
)
from services.security.zero_trust import ZeroTrustEngine, SecurityContext
from services.security.vault_manager import VaultManager, SecretScope
from services.security.kms import KeyManagementService, KMSProvider
from services.security.key_rotation import KeyRotationManager
from services.security.encryption import EncryptionEngine
from services.security.token_manager import TokenManager
from services.security.audit_center import AuditCenter, AuditAction
from services.security.compliance import ComplianceCenter, ComplianceFramework
from services.security.policy_engine import PolicyEngine, PolicyEffect
from services.security.governance import GovernanceCenter, GovernanceCategory, RiskLevel

logger = logging.getLogger(__name__)


class SecurityService:
    """
    Unified Security Service Facade.

    Provides a single entry point for all security operations:
    authentication, authorization, encryption, audit, compliance,
    governance, and policy enforcement.
    """

    def __init__(self):
        self.authentication = AuthenticationService()
        self.authorization = AuthorizationService()
        self.zero_trust = ZeroTrustEngine()
        self.vault = VaultManager()
        self.kms = KeyManagementService(KMSProvider.LOCAL)
        self.key_rotation = KeyRotationManager()
        self.encryption = EncryptionEngine()
        self.token_manager = TokenManager()
        self.audit = AuditCenter()
        self.compliance = ComplianceCenter()
        self.policy_engine = PolicyEngine()
        self.governance = GovernanceCenter()

        self._initialized = False
        self._init_default_config()

    def _init_default_config(self):
        self._init_encryption()
        self._init_audit_categories()
        self._init_policies()
        self._initialized = True
        logger.info("Security service initialized")

    def _init_encryption(self):
        import secrets
        key = secrets.token_bytes(32)
        self.encryption.set_encryption_key("default", key)

        from services.security.encryption import FieldEncryption, EncryptionAlgorithm
        self.encryption.register_field(FieldEncryption(
            field_name="account_number",
            algorithm=EncryptionAlgorithm.AES_256_GCM,
            key_name="default",
            searchable=True,
        ))
        self.encryption.register_field(FieldEncryption(
            field_name="ssn",
            algorithm=EncryptionAlgorithm.AES_256_GCM,
            key_name="default",
        ))
        self.encryption.register_field(FieldEncryption(
            field_name="credit_card",
            algorithm=EncryptionAlgorithm.AES_256_GCM,
            key_name="default",
        ))

    def _init_audit_categories(self):
        pass

    def _init_policies(self):
        from services.security.policy_engine import Policy, PolicyStatement, PolicyCondition
        default_policy = Policy(
            name="Allow Authenticated Internal",
            enabled=True,
            priority=100,
            statements=[
                PolicyStatement(
                    effect=PolicyEffect.ALLOW,
                    conditions=[
                        PolicyCondition("user_id", "exists", True),
                        PolicyCondition("environment", "eq", "internal"),
                    ],
                ),
            ],
        )
        self.policy_engine.create_policy(default_policy)

        deny_prod_delete = Policy(
            name="Deny Production Delete",
            enabled=True,
            priority=50,
            statements=[
                PolicyStatement(
                    effect=PolicyEffect.DENY,
                    conditions=[
                        PolicyCondition("environment", "eq", "production"),
                        PolicyCondition("action", "eq", "delete"),
                    ],
                ),
            ],
        )
        self.policy_engine.create_policy(deny_prod_delete)

        deny_ai_risk_modify = Policy(
            name="Deny AI Agent Risk Modify",
            enabled=True,
            priority=60,
            statements=[
                PolicyStatement(
                    effect=PolicyEffect.DENY,
                    conditions=[
                        PolicyCondition("service", "eq", "ai_agent"),
                        PolicyCondition("action", "contains", "risk"),
                    ],
                ),
            ],
        )
        self.policy_engine.create_policy(deny_ai_risk_modify)

    def authenticate(
        self,
        username: str,
        password: str,
        mfa_code: Optional[str] = None,
        ip_address: str = "",
    ):
        session = self.authentication.authenticate(
            username=username,
            password=password,
            mfa_code=mfa_code,
            ip_address=ip_address,
        )
        self.audit.log(
            action=AuditAction.LOGIN,
            actor=username,
            severity=self._determine_severity(username),
            ip_address=ip_address,
        )
        return session

    def authorize(
        self,
        user_id: str,
        resource: ResourceType,
        permission: Permission,
        context: Optional[Dict] = None,
    ) -> bool:
        return self.authorization.check_permission(user_id, resource, permission, context)

    def check_request(
        self,
        context: SecurityContext,
    ):
        zt_decision = self.zero_trust.evaluate(context)
        policy_decision = self.policy_engine.evaluate(context.to_dict())
        return zt_decision, policy_decision

    def get_status(self) -> Dict:
        return {
            "security": "healthy",
            "authentication": "enabled",
            "authorization": "enabled",
            "zeroTrust": "enabled",
            "encryption": "enabled",
            "audit": "enabled",
            "compliance": "enabled",
            "governance": "enabled",
            "policy": "enabled",
            "vault": "connected",
            "kms": "active",
            "initialized": self._initialized,
            "timestamp": datetime.now().isoformat(),
        }

    def _determine_severity(self, username: str):
        from services.security.audit_center import AuditSeverity
        if username == "admin":
            return AuditSeverity.HIGH
        return AuditSeverity.INFO
