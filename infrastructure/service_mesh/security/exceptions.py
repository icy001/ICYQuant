"""Security exceptions for ICYQuant Service Mesh.

Provides exception classes for security-related errors including
identity, certificate, mTLS, authentication, and authorization failures.
"""

from __future__ import annotations

from typing import Optional


class SecurityError(Exception):
    """Base security error."""

    def __init__(self, message: str = "", details: Optional[dict] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class IdentityError(SecurityError):
    """Identity-related error."""


class WorkloadIdentityError(IdentityError):
    """Workload identity error."""


class TrustDomainError(IdentityError):
    """Trust domain error."""


class SPIFFEError(IdentityError):
    """SPIFFE identity error."""


class CertificateError(SecurityError):
    """Certificate-related error."""


class CertificateIssueError(CertificateError):
    """Certificate issuance error."""


class CertificateValidationError(CertificateError):
    """Certificate validation error."""


class CertificateRevocationError(CertificateError):
    """Certificate revocation error."""


class CertificateRotationError(CertificateError):
    """Certificate rotation error."""


class CertificateExpiredError(CertificateError):
    """Certificate expired error."""


class MTLSError(SecurityError):
    """mTLS handshake or connection error."""


class HandshakeError(MTLSError):
    """TLS handshake error."""


class AuthenticationError(SecurityError):
    """Authentication failure."""


class AuthorizationError(SecurityError):
    """Authorization failure — access denied."""


class PolicyError(SecurityError):
    """Policy evaluation error."""


class PolicyNotFoundError(PolicyError):
    """Policy not found."""


class KeyError_(SecurityError):
    """Key management error."""


class SecretError(SecurityError):
    """Secret provider error."""


class TokenError(SecurityError):
    """Token provider error."""


class AuditError(SecurityError):
    """Audit logging error."""


class SecurityManagerError(SecurityError):
    """Security manager initialization or runtime error."""


__all__ = [
    "SecurityError",
    "IdentityError",
    "WorkloadIdentityError",
    "TrustDomainError",
    "SPIFFEError",
    "CertificateError",
    "CertificateIssueError",
    "CertificateValidationError",
    "CertificateRevocationError",
    "CertificateRotationError",
    "CertificateExpiredError",
    "MTLSError",
    "HandshakeError",
    "AuthenticationError",
    "AuthorizationError",
    "PolicyError",
    "PolicyNotFoundError",
    "KeyError_",
    "SecretError",
    "TokenError",
    "AuditError",
    "SecurityManagerError",
]
