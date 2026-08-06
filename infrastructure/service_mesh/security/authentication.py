"""Authentication for ICYQuant Service Mesh.

Provides ``AuthenticationManager`` for certificate, token, identity,
and workload-based authentication, producing authenticated principals.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, Optional

from .principal import Principal
from .exceptions import AuthenticationError
from .token_provider import TokenProvider

logger = logging.getLogger(__name__)


class AuthMethod(str):
    """Authentication methods."""

    CERTIFICATE = "certificate"
    TOKEN = "token"
    IDENTITY = "identity"
    WORKLOAD = "workload"


class AuthResult:
    """Result of authentication."""

    def __init__(self, success: bool, principal: Optional[Principal] = None, method: str = "", error: str = "") -> None:
        self.success = success
        self.principal = principal
        self.method = method
        self.error = error
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "principal": self.principal.to_dict() if self.principal else None,
            "method": self.method,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


class AuthenticationManager:
    """Manages authentication for the mesh."""

    def __init__(self, token_provider: Optional[TokenProvider] = None) -> None:
        self._lock = threading.RLock()
        self._token_provider = token_provider or TokenProvider()
        self._auth_count = 0
        self._success_count = 0
        self._failure_count = 0

    async def authenticate(
        self,
        method: str,
        credentials: Dict[str, Any],
    ) -> AuthResult:
        """Authenticate a request using the specified method."""
        with self._lock:
            self._auth_count += 1

        if method == AuthMethod.CERTIFICATE:
            return await self._auth_certificate(credentials)
        elif method == AuthMethod.TOKEN:
            return await self._auth_token(credentials)
        elif method == AuthMethod.IDENTITY:
            return await self._auth_identity(credentials)
        elif method == AuthMethod.WORKLOAD:
            return await self._auth_workload(credentials)
        else:
            return AuthResult(success=False, method=method, error="unknown_method")

    async def _auth_certificate(self, credentials: Dict[str, Any]) -> AuthResult:
        cert_id = credentials.get("cert_id", "")
        spiffe_id = credentials.get("spiffe_id", "")
        if not cert_id and not spiffe_id:
            return AuthResult(success=False, method=AuthMethod.CERTIFICATE, error="no_certificate")
        principal = Principal.from_spiffe_id(spiffe_id or f"spiffe://icyquant.local/default/{cert_id}")
        principal.mark_authenticated(AuthMethod.CERTIFICATE)
        with self._lock:
            self._success_count += 1
        return AuthResult(success=True, principal=principal, method=AuthMethod.CERTIFICATE)

    async def _auth_token(self, credentials: Dict[str, Any]) -> AuthResult:
        token = credentials.get("token", "")
        if not token:
            return AuthResult(success=False, method=AuthMethod.TOKEN, error="no_token")
        if not self._token_provider.validate_token(token):
            return AuthResult(success=False, method=AuthMethod.TOKEN, error="invalid_token")
        record = self._token_provider.get_token(token)
        principal = Principal(
            principal_id=record.principal if record else "unknown",
            spiffe_id=record.principal if record else "",
        )
        principal.mark_authenticated(AuthMethod.TOKEN)
        with self._lock:
            self._success_count += 1
        return AuthResult(success=True, principal=principal, method=AuthMethod.TOKEN)

    async def _auth_identity(self, credentials: Dict[str, Any]) -> AuthResult:
        spiffe_id = credentials.get("spiffe_id", "")
        if not spiffe_id:
            return AuthResult(success=False, method=AuthMethod.IDENTITY, error="no_identity")
        principal = Principal.from_spiffe_id(spiffe_id)
        principal.mark_authenticated(AuthMethod.IDENTITY)
        with self._lock:
            self._success_count += 1
        return AuthResult(success=True, principal=principal, method=AuthMethod.IDENTITY)

    async def _auth_workload(self, credentials: Dict[str, Any]) -> AuthResult:
        service_name = credentials.get("service_name", "")
        namespace = credentials.get("namespace", "default")
        if not service_name:
            return AuthResult(success=False, method=AuthMethod.WORKLOAD, error="no_service_name")
        spiffe_id = f"spiffe://icyquant.local/{namespace}/{service_name}"
        principal = Principal.from_spiffe_id(spiffe_id)
        principal.mark_authenticated(AuthMethod.WORKLOAD)
        with self._lock:
            self._success_count += 1
        return AuthResult(success=True, principal=principal, method=AuthMethod.WORKLOAD)

    @property
    def token_provider(self) -> TokenProvider:
        return self._token_provider

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "auth_count": self._auth_count,
                "success_count": self._success_count,
                "failure_count": self._failure_count,
            }
