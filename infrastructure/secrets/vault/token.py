"""
Vault Token authenticator.

Implements static token-based authentication
for Vault, suitable for development/testing
and systems with pre-provisioned tokens.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from .client import VaultClient
from .config import VaultTokenConfig
from .exceptions import VaultAuthenticationError
from .authenticator import VaultAuthenticator

logger = logging.getLogger(__name__)


class TokenAuthenticator(VaultAuthenticator):
    """
    Static token-based Vault authenticator.

    Uses a pre-existing Vault token for
    authentication. Supports token renewal
    and revocation.

    Usage:
        config = VaultTokenConfig(token="s.abc123")
        auth = TokenAuthenticator(config)
        result = await auth.login(client)
    """

    name = "token"

    def __init__(self, config: VaultTokenConfig) -> None:
        super().__init__()
        self._config = config
        self._token = config.token

    async def login(self, client: VaultClient) -> Dict[str, Any]:
        """
        Validate and use the static token.

        Looks up token metadata to validate
        the token and extract renewal info.

        Args:
            client: Vault HTTP client.

        Returns:
            Dict with token and metadata.
        """
        if not self._token:
            raise VaultAuthenticationError(
                "No token configured for token authentication"
            )

        client.set_token(self._token)

        try:
            lookup = await client.token_lookup()
            auth_data = lookup.get("data", {})

            self._logged_in = True
            self._renewable = auth_data.get("renewable", self._config.renew)
            self._metadata = {
                "accessor": auth_data.get("accessor", ""),
                "policies": auth_data.get("policies", []),
                "display_name": auth_data.get("display_name", ""),
                "entity_id": auth_data.get("entity_id", ""),
            }

            # Compute expiry
            create_time = auth_data.get("creation_time")
            ttl = auth_data.get("ttl", 0)
            if create_time and ttl:
                self._expires_at = datetime.utcfromtimestamp(create_time + ttl)

            logger.info(
                "Token authenticated: accessor=%s, renewable=%s",
                self._metadata.get("accessor", "?"),
                self._renewable,
            )

            return {
                "token": self._token,
                "renewable": self._renewable,
                "metadata": self._metadata,
            }

        except Exception as e:
            raise VaultAuthenticationError(
                f"Token authentication failed: {e}"
            ) from e

    async def logout(self, client: VaultClient) -> None:
        """Revoke the token."""
        await super().logout(client)

    def get_status(self) -> Dict[str, Any]:
        """Get token authenticator status."""
        status = super().get_status()
        status["accessor"] = self._metadata.get("accessor", "")
        status["policies"] = self._metadata.get("policies", [])
        return status
