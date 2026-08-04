"""
Vault authenticator base class.

Defines the unified interface for all
Vault authentication methods, supporting
Token, AppRole, Kubernetes, and JWT/OIDC.
"""

from __future__ import annotations

import abc
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from .client import VaultClient
from .exceptions import VaultAuthenticationError

logger = logging.getLogger(__name__)


class VaultAuthenticator(abc.ABC):
    """
    Abstract Vault authenticator.

    All Vault authentication backends must
    implement this interface to provide
    consistent login/logout behavior.

    Usage:
        auth = AppRoleAuthenticator(config)
        token, meta = await auth.login(client)
        client.set_token(token)
    """

    name: str = "base"

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._metadata: Dict[str, Any] = {}
        self._logged_in: bool = False
        self._expires_at: Optional[datetime] = None
        self._renewable: bool = False

    @abc.abstractmethod
    async def login(self, client: VaultClient) -> Dict[str, Any]:
        """
        Authenticate with Vault and obtain a token.

        Args:
            client: Vault HTTP client.

        Returns:
            Dict with 'token' and authentication metadata.
        """
        ...

    async def logout(self, client: VaultClient) -> None:
        """
        Revoke the current authentication token.

        Args:
            client: Vault HTTP client.
        """
        if self._logged_in and self._token:
            try:
                client.set_token(self._token)
                await client.token_revoke()
            except Exception as e:
                logger.warning("Logout failed: %s", e)
            finally:
                self._token = None
                self._logged_in = False
                self._metadata = {}

    async def renew(self, client: VaultClient, increment: int = 3600) -> Dict[str, Any]:
        """
        Renew the current authentication token.

        Args:
            client: Vault HTTP client.
            increment: Renewal increment in seconds.

        Returns:
            Renewal response data.
        """
        if not self._logged_in or not self._token:
            raise VaultAuthenticationError("Not authenticated")

        client.set_token(self._token)
        result = await client.token_renew(increment=increment)

        self._expires_at = self._compute_expiry(result, increment)
        return result

    def _compute_expiry(
        self,
        result: Dict[str, Any],
        default_increment: int,
    ) -> datetime:
        """Compute token expiry from renewal result."""
        auth_data = result.get("auth", {})
        lease_duration = auth_data.get("lease_duration", default_increment)
        return datetime.utcfromtimestamp(datetime.utcnow().timestamp() + lease_duration)

    # ── Status ──

    @property
    def is_logged_in(self) -> bool:
        """Check if currently authenticated."""
        return self._logged_in

    @property
    def token(self) -> Optional[str]:
        """Get current token."""
        return self._token

    @property
    def expires_at(self) -> Optional[datetime]:
        """Get token expiration time."""
        return self._expires_at

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        if self._expires_at is None:
            return False
        return datetime.utcnow() > self._expires_at

    @property
    def is_renewable(self) -> bool:
        """Check if token is renewable."""
        return self._renewable

    def get_status(self) -> Dict[str, Any]:
        """Get authenticator status."""
        return {
            "name": self.name,
            "logged_in": self._logged_in,
            "expires_at": self._expires_at.isoformat() if self._expires_at else None,
            "is_expired": self.is_expired,
            "renewable": self._renewable,
            "metadata": self._metadata,
        }
