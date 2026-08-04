"""
Vault AppRole authenticator.

Implements AppRole-based authentication
for Vault, suitable for workloads like
OMS, Risk Engine, Strategy Service,
and Execution Engine.

Security model:
- Role ID: Static identifier for the role
- Secret ID: Dynamic credential (renewable, single-use)
- Token: Generated on successful login
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime
from typing import Any, Dict, Optional

from .client import VaultClient
from .config import VaultAppRoleConfig
from .exceptions import VaultAuthenticationError
from .authenticator import VaultAuthenticator

logger = logging.getLogger(__name__)


class AppRoleAuthenticator(VaultAuthenticator):
    """
    AppRole-based Vault authenticator.

    Authenticates using a Role ID and Secret ID
    pair, providing identity-based access
    for services and workloads.

    Usage:
        config = VaultAppRoleConfig(
            role_id="my-role-id",
            secret_id="my-secret-id",
        )
        auth = AppRoleAuthenticator(config)
        result = await auth.login(client)
    """

    name = "approle"

    def __init__(self, config: VaultAppRoleConfig) -> None:
        super().__init__()
        self._config = config
        self._role_id = config.role_id
        self._secret_id = config.secret_id
        self._mount = config.mount_point

    async def login(self, client: VaultClient) -> Dict[str, Any]:
        """
        Authenticate using AppRole credentials.

        Args:
            client: Vault HTTP client.

        Returns:
            Dict with token and metadata.
        """
        if not self._role_id or not self._secret_id:
            raise VaultAuthenticationError(
                "AppRole requires both role_id and secret_id"
            )

        path = f"/auth/{self._mount}/login"
        payload = {
            "role_id": self._role_id,
            "secret_id": self._secret_id,
        }

        try:
            result = await client.write(path, payload=payload)
            auth_data = result.get("auth", {})

            self._token = auth_data.get("client_token", "")
            self._logged_in = True
            self._renewable = auth_data.get("renewable", True)

            lease_duration = auth_data.get("lease_duration", 3600)
            self._expires_at = datetime.utcfromtimestamp(
                datetime.utcnow().timestamp() + lease_duration
            )

            self._metadata = {
                "role_id": self._role_id,
                "policies": auth_data.get("policies", []),
                "metadata": auth_data.get("metadata", {}),
                "lease_duration": lease_duration,
                "renewable": self._renewable,
            }

            # Set token on client
            client.set_token(self._token)

            logger.info(
                "AppRole authenticated: role_id=%s, expires=%s",
                self._role_id,
                self._expires_at.isoformat() if self._expires_at else "never",
            )

            return {
                "token": self._token,
                "renewable": self._renewable,
                "expires_at": self._expires_at.isoformat() if self._expires_at else None,
                "metadata": self._metadata,
            }

        except Exception as e:
            raise VaultAuthenticationError(
                f"AppRole authentication failed: {e}"
            ) from e

    def rotate_secret_id(self) -> str:
        """
        Generate a new secret ID for rotation.

        Returns:
            New secret ID string.
        """
        new_secret_id = secrets.token_urlsafe(32)
        self._secret_id = new_secret_id
        self._config.secret_id = new_secret_id
        logger.info("AppRole secret ID rotated")
        return new_secret_id

    def get_status(self) -> Dict[str, Any]:
        """Get AppRole authenticator status."""
        status = super().get_status()
        status["role_id"] = self._role_id
        status["has_secret_id"] = bool(self._secret_id)
        return status
