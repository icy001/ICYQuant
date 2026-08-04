"""
Vault-specific exceptions.

Extends the base secrets exception hierarchy
with Vault-specific error types.
"""

from __future__ import annotations

from typing import Any, Optional


class VaultError(Exception):
    """Base Vault operation error."""

    def __init__(
        self,
        message: str = "",
        status_code: Optional[int] = None,
        path: str = "",
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.path = path
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "error": self.message,
            "status_code": self.status_code,
            "path": self.path,
        }


class VaultConnectionError(VaultError):
    """Cannot connect to Vault server."""


class VaultAuthenticationError(VaultError):
    """Authentication failure with Vault."""


class VaultPermissionDeniedError(VaultError):
    """Permission denied for Vault operation."""


class VaultSecretNotFoundError(VaultError):
    """Secret not found in Vault."""


class VaultWriteError(VaultError):
    """Failed to write secret to Vault."""


class VaultLeaseError(VaultError):
    """Lease-related error."""


class VaultRenewalError(VaultLeaseError):
    """Lease renewal failed."""


class VaultRevocationError(VaultError):
    """Secret revocation failed."""


class VaultNamespaceError(VaultError):
    """Namespace operation error."""


class VaultHealthError(VaultError):
    """Vault health check failure."""


class VaultFailoverError(VaultError):
    """Failover operation error."""


class VaultCircuitOpenError(VaultError):
    """Circuit breaker is open for Vault cluster."""
