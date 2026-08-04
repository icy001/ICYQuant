"""
Secrets platform exceptions.

Defines the exception hierarchy for
the secrets management platform,
enabling precise error handling for
secret-related operations.
"""

from __future__ import annotations

from typing import List, Optional


class SecretsError(Exception):
    """Base exception for all secrets platform errors."""


class SecretNotFoundError(SecretsError):
    """Raised when a secret key is not found."""

    def __init__(self, key: str, namespace: str = "default") -> None:
        self.key = key
        self.namespace = namespace
        super().__init__(f"Secret not found: {namespace}/{key}")


class SecretAccessDeniedError(SecretsError):
    """Raised when access to a secret is denied."""

    def __init__(
        self,
        key: str,
        role: str = "",
        reason: str = "",
    ) -> None:
        self.key = key
        self.role = role
        self.reason = reason
        msg = f"Access denied to secret: {key}"
        if role:
            msg += f" (role: {role})"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class SecretValidationError(SecretsError):
    """Raised when secret validation fails."""

    def __init__(
        self,
        key: str,
        errors: Optional[List[str]] = None,
    ) -> None:
        self.key = key
        self.errors = errors or []
        super().__init__(
            f"Validation failed for secret '{key}': {', '.join(self.errors)}"
        )


class SecretEncryptionError(SecretsError):
    """Raised when secret encryption/decryption fails."""

    def __init__(self, key: str, reason: str = "") -> None:
        self.key = key
        self.reason = reason
        msg = f"Encryption error for secret: {key}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class SecretExpiredError(SecretsError):
    """Raised when a secret has expired."""

    def __init__(self, key: str, expires_at: str = "") -> None:
        self.key = key
        self.expires_at = expires_at
        msg = f"Secret expired: {key}"
        if expires_at:
            msg += f" (expired at: {expires_at})"
        super().__init__(msg)


class SecretProviderError(SecretsError):
    """Raised when a secrets provider operation fails."""

    def __init__(
        self,
        provider: str,
        operation: str,
        reason: str = "",
    ) -> None:
        self.provider = provider
        self.operation = operation
        self.reason = reason
        msg = f"Provider '{provider}' operation '{operation}' failed"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class SecretCacheError(SecretsError):
    """Raised when secret cache operations fail."""


class SecretPolicyError(SecretsError):
    """Raised when an access policy violation occurs."""

    def __init__(self, key: str, policy: str, reason: str = "") -> None:
        self.key = key
        self.policy = policy
        self.reason = reason
        msg = f"Policy violation for secret '{key}': {policy}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class SecretRotationError(SecretsError):
    """Raised when secret rotation fails."""

    def __init__(self, key: str, reason: str = "") -> None:
        self.key = key
        self.reason = reason
        msg = f"Rotation failed for secret: {key}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class SecretResolutionError(SecretsError):
    """Raised when secret reference resolution fails."""

    def __init__(self, reference: str, reason: str = "") -> None:
        self.reference = reference
        self.reason = reason
        msg = f"Failed to resolve secret reference: {reference}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)
