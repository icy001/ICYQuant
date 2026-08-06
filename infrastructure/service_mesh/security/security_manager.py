"""Security Manager for ICYQuant Service Mesh.

Provides ``SecurityManager`` as the unified entry point for zero-trust
security, coordinating identity, certificates, policies, secrets,
mTLS, and audit across the mesh.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Dict, List, Optional

from .audit import SecurityAudit
from .authentication import AuthenticationManager, AuthMethod
from .authorization import AuthorizationManager
from .certificate_manager import CertificateManager
from .certificate_rotator import CertificateRotator
from .certificate_validator import CertificateValidator
from .diagnostics import SecurityDiagnostics
from .health import SecurityHealth
from .identity import IdentityService
from .key_manager import KeyManager
from .metrics import SecurityMetrics
from .mtls import MTLSEngine
from .policy_engine import PolicyEngine, SecurityPolicy, PolicyEffect
from .policy_repository import PolicyRepository
from .principal import Principal
from .revocation import RevocationManager
from .secret_provider import SecretProvider
from .spiffe import SPIFFEManager
from .telemetry import SecurityTelemetry
from .token_provider import TokenProvider
from .trust_domain import TrustDomain, TrustDomainManager
from .workload_identity import WorkloadIdentityManager

logger = logging.getLogger(__name__)


class SecurityManager:
    """Unified security management entry point."""

    def __init__(self, trust_domain: str = "icyquant.local") -> None:
        self._lock = threading.RLock()
        self._started = False
        self._trust_domain = trust_domain

        # Identity layer
        self._trust_domain_mgr = TrustDomainManager(
            TrustDomain(name=trust_domain)
        )
        self._identity_service = IdentityService()
        self._workload_mgr = WorkloadIdentityManager(self._identity_service)
        self._spiffe_mgr = SPIFFEManager()

        # Certificate layer
        self._cert_manager = CertificateManager()
        self._cert_validator = CertificateValidator()
        self._cert_rotator = CertificateRotator(self._cert_manager)
        self._revocation_mgr = RevocationManager()

        # Key/Secret layer
        self._key_manager = KeyManager()
        self._secret_provider = SecretProvider()
        self._token_provider = TokenProvider()

        # mTLS layer
        self._mtls_engine = MTLSEngine(
            cert_manager=self._cert_manager,
        )

        # Auth/Policy layer
        self._policy_engine = PolicyEngine()
        self._policy_repo = PolicyRepository()
        self._auth_mgr = AuthenticationManager(self._token_provider)
        self._authz_mgr = AuthorizationManager(self._policy_engine)

        # Observability
        self._metrics = SecurityMetrics()
        self._telemetry = SecurityTelemetry()
        self._health = SecurityHealth()
        self._diagnostics = SecurityDiagnostics()
        self._audit = SecurityAudit()

        # Register health checks
        self._health.register_check(
            "cert_manager", lambda: self._cert_manager.is_running
        )
        self._health.register_check(
            "mtls_engine", lambda: self._mtls_engine.is_running
        )
        self._health.register_check(
            "secret_provider", lambda: self._secret_provider.is_running
        )
        self._health.register_check(
            "identity_service",
            lambda: len(self._identity_service.list_identities()) >= 0,
        )

    async def initialize(self) -> Dict[str, Any]:
        """Initialize the security manager."""
        self._cert_manager.start()
        self._secret_provider.start()
        self._mtls_engine.start()
        self._started = True

        self._telemetry.log_security_event(
            "security_manager_initialized",
            "security_manager",
        )
        logger.info("SecurityManager initialized")
        return {"success": True, "trust_domain": self._trust_domain}

    async def shutdown(self) -> Dict[str, Any]:
        """Shutdown the security manager."""
        await self._cert_rotator.stop()
        self._mtls_engine.stop()
        self._cert_manager.stop()
        self._secret_provider.stop()
        self._started = False
        logger.info("SecurityManager shutdown")
        return {"success": True}

    async def authenticate(
        self,
        method: str,
        credentials: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Authenticate a request."""
        self._metrics.increment_auth({"method": method})
        result = await self._auth_mgr.authenticate(method, credentials)

        self._telemetry.log_authentication(
            principal=result.principal.spiffe_id if result.principal else "unknown",
            method=method,
            success=result.success,
        )
        self._audit.record_authentication(
            principal=result.principal.spiffe_id if result.principal else "unknown",
            success=result.success,
            method=method,
        )
        if not result.success:
            self._metrics.increment_denied({"reason": "auth_failed"})
        return result.to_dict()

    async def authorize(
        self,
        principal: Principal,
        resource: str,
        action: str = "access",
    ) -> Dict[str, Any]:
        """Authorize a request."""
        self._metrics.increment_authorization({"resource": resource})
        result = await self._authz_mgr.authorize(principal, resource, action)

        self._telemetry.log_authorization(
            principal=principal.spiffe_id,
            resource=resource,
            action=action,
            allowed=result.allowed,
            policy_id=result.policy_id,
        )
        self._audit.record_authorization(
            principal=principal.spiffe_id,
            resource=resource,
            allowed=result.allowed,
            policy_id=result.policy_id,
        )
        if not result.allowed:
            self._metrics.increment_denied({"reason": "authz_denied"})
        return result.to_dict()

    async def create_workload_identity(
        self,
        service_name: str,
        namespace: str = "default",
        instance_id: str = "",
        ttl_seconds: int = 3600,
    ) -> Dict[str, Any]:
        """Create a workload identity."""
        self._metrics.increment_identity({"service": service_name})
        wi = self._workload_mgr.create_identity(
            service_name=service_name,
            namespace=namespace,
            trust_domain=self._trust_domain,
            instance_id=instance_id,
            ttl_seconds=ttl_seconds,
        )
        self._diagnostics.register_identity(wi.identity_id, wi.to_dict())
        self._audit.record(
            event_type="identity_create",
            actor=service_name,
            resource=wi.spiffe_id,
        )
        return wi.to_dict()

    async def issue_certificate(
        self,
        spiffe_id: str,
        cert_type: str = "workload",
        ttl_hours: int = 24,
    ) -> Dict[str, Any]:
        """Issue a certificate for a workload."""
        self._metrics.increment_certificate_issue({"spiffe_id": spiffe_id})
        cert = await self._cert_manager.issue(
            spiffe_id=spiffe_id,
            cert_type=cert_type,
            ttl_hours=ttl_hours,
        )
        self._diagnostics.register_certificate(cert.cert_id, cert.to_dict())
        self._audit.record_certificate_issue(
            cert_id=cert.cert_id,
            principal=spiffe_id,
            ca_id=self._cert_manager.ca.ca_id,
        )
        self._telemetry.log_certificate_event("issued", cert.cert_id)
        self._metrics.set_active_certificates(
            len(self._cert_manager.list_certificates())
        )
        return cert.to_dict()

    async def establish_mtls(
        self,
        client_identity: str,
        server_identity: str,
        client_cert=None,
        server_cert=None,
    ) -> Dict[str, Any]:
        """Establish a mutual TLS connection."""
        self._metrics.increment_mtls_handshake()
        result = await self._mtls_engine.establish(
            client_identity=client_identity,
            server_identity=server_identity,
            client_cert=client_cert,
            server_cert=server_cert,
        )
        self._telemetry.log_mtls_handshake(
            client_identity=client_identity,
            server_identity=server_identity,
            success=result.get("success", False),
        )
        if result.get("success"):
            session = self._mtls_engine.get_session(result["session_id"])
            if session:
                self._diagnostics.register_mtls_session(
                    session.session_id, session.to_dict()
                )
        return result

    def register_policy(self, policy: SecurityPolicy) -> None:
        """Register a security policy."""
        self._policy_engine.register_policy(policy)
        self._policy_repo.add(policy)
        self._audit.record_policy_change(
            policy_id=policy.policy_id,
            change="registered",
        )

    def get_policy(self, policy_id: str) -> Optional[SecurityPolicy]:
        return self._policy_engine.get_policy(policy_id)

    def list_policies(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self._policy_engine.list_policies()]

    async def health_check(self) -> Dict[str, Any]:
        return await self._health.check()

    @property
    def is_running(self) -> bool:
        return self._started

    @property
    def cert_manager(self) -> CertificateManager:
        return self._cert_manager

    @property
    def mtls_engine(self) -> MTLSEngine:
        return self._mtls_engine

    @property
    def policy_engine(self) -> PolicyEngine:
        return self._policy_engine

    @property
    def auth_manager(self) -> AuthenticationManager:
        return self._auth_mgr

    @property
    def authz_manager(self) -> AuthorizationManager:
        return self._authz_mgr

    @property
    def workload_manager(self) -> WorkloadIdentityManager:
        return self._workload_mgr

    @property
    def trust_domain_manager(self) -> TrustDomainManager:
        return self._trust_domain_mgr

    @property
    def metrics(self) -> SecurityMetrics:
        return self._metrics

    @property
    def audit(self) -> SecurityAudit:
        return self._audit

    @property
    def diagnostics(self) -> SecurityDiagnostics:
        return self._diagnostics

    @property
    def telemetry(self) -> SecurityTelemetry:
        return self._telemetry

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "started": self._started,
                "trust_domain": self._trust_domain,
                "metrics": self._metrics.get_summary(),
                "identity": self._workload_mgr.get_stats(),
                "certificates": self._cert_manager.get_stats(),
                "mtls": self._mtls_engine.get_stats(),
                "policies": self._policy_engine.get_stats(),
                "audit": self._audit.get_stats(),
                "health": self._health.get_stats(),
                "diagnostics": self._diagnostics.get_snapshot(),
            }
