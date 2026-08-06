"""Security module for ICYQuant Service Mesh.

Provides zero-trust security capabilities including workload identity,
SPIFFE-style identity, certificate authority, mTLS engine, policy
engine, and security audit.
"""

# Exceptions
from .exceptions import (
    SecurityError,
    IdentityError,
    WorkloadIdentityError,
    TrustDomainError,
    SPIFFEError,
    CertificateError,
    CertificateIssueError,
    CertificateValidationError,
    CertificateRevocationError,
    CertificateRotationError,
    CertificateExpiredError,
    MTLSError,
    HandshakeError,
    AuthenticationError,
    AuthorizationError,
    PolicyError,
    PolicyNotFoundError,
    KeyError_,
    SecretError,
    TokenError,
    AuditError,
    SecurityManagerError,
)

# Foundational
from .metrics import SecurityMetrics
from .telemetry import SecurityTelemetry
from .health import SecurityHealth
from .diagnostics import SecurityDiagnostics
from .audit import AuditEventType, AuditSeverity, AuditRecord, SecurityAudit

# Identity
from .identity import Identity, IdentityService, IdentityStatus
from .workload_identity import WorkloadIdentity, WorkloadIdentityManager
from .principal import Principal, PrincipalStore
from .trust_domain import TrustDomain, TrustDomainManager, TrustDomainLevel
from .spiffe import SPIFFEID, SPIFFEBundle, SPIFFEManager

# Certificate
from .certificate_authority import (
    CertificateAuthority,
    CertificateRecord,
    CertificateType,
)
from .certificate_store import CertificateStore
from .certificate_manager import (
    CertificateManager,
    CertificateState,
)
from .certificate_rotator import (
    CertificateRotator,
    RotationType,
)
from .certificate_validator import (
    CertificateValidator,
    ValidationResult,
)
from .revocation import (
    RevocationManager,
    RevocationEntry,
    RevocationReason,
)

# Key/Secret
from .key_manager import KeyManager, KeyRecord, KeyType
from .secret_provider import SecretProvider, SecretRecord
from .token_provider import TokenProvider, TokenRecord

# mTLS
from .handshake import (
    HandshakeManager,
    HandshakeSession,
    HandshakeState,
)
from .mtls import MTLSEngine, MTLSSession

# Auth/Policy
from .authentication import (
    AuthenticationManager,
    AuthMethod,
    AuthResult,
)
from .authorization import (
    AuthorizationManager,
    AuthzResult,
)
from .policy_engine import (
    PolicyEngine,
    SecurityPolicy,
    PolicyEffect,
)
from .policy_repository import (
    PolicyRepository,
    PolicyVersion,
)

# Orchestration
from .security_manager import SecurityManager
from .scheduler import SecurityScheduler, SecurityScheduledTask

__all__ = [
    # Exceptions
    "SecurityError", "IdentityError", "WorkloadIdentityError",
    "TrustDomainError", "SPIFFEError", "CertificateError",
    "CertificateIssueError", "CertificateValidationError",
    "CertificateRevocationError", "CertificateRotationError",
    "CertificateExpiredError", "MTLSError", "HandshakeError",
    "AuthenticationError", "AuthorizationError", "PolicyError",
    "PolicyNotFoundError", "KeyError_", "SecretError", "TokenError",
    "AuditError", "SecurityManagerError",
    # Foundational
    "SecurityMetrics", "SecurityTelemetry", "SecurityHealth",
    "SecurityDiagnostics", "AuditEventType", "AuditSeverity",
    "AuditRecord", "SecurityAudit",
    # Identity
    "Identity", "IdentityService", "IdentityStatus",
    "WorkloadIdentity", "WorkloadIdentityManager",
    "Principal", "PrincipalStore",
    "TrustDomain", "TrustDomainManager", "TrustDomainLevel",
    "SPIFFEID", "SPIFFEBundle", "SPIFFEManager",
    # Certificate
    "CertificateAuthority", "CertificateRecord", "CertificateType",
    "CertificateStore", "CertificateManager", "CertificateState",
    "CertificateRotator", "RotationType",
    "CertificateValidator", "ValidationResult",
    "RevocationManager", "RevocationEntry", "RevocationReason",
    # Key/Secret
    "KeyManager", "KeyRecord", "KeyType",
    "SecretProvider", "SecretRecord",
    "TokenProvider", "TokenRecord",
    # mTLS
    "HandshakeManager", "HandshakeSession", "HandshakeState",
    "MTLSEngine", "MTLSSession",
    # Auth/Policy
    "AuthenticationManager", "AuthMethod", "AuthResult",
    "AuthorizationManager", "AuthzResult",
    "PolicyEngine", "SecurityPolicy", "PolicyEffect",
    "PolicyRepository", "PolicyVersion",
    # Orchestration
    "SecurityManager", "SecurityScheduler", "SecurityScheduledTask",
]
