"""
Vault JWT/OIDC authenticator.

Implements JWT-based and OIDC authentication
for Vault, suitable for CI/CD pipelines
(GitHub Actions, GitLab CI) and automation
workflows.

Authentication methods:
- JWT: Signed JWT tokens from trusted issuers
- OIDC: OAuth2 identity provider integration
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from .client import VaultClient
from .config import VaultJWTConfig
from .exceptions import VaultAuthenticationError
from .authenticator import VaultAuthenticator

logger = logging.getLogger(__name__)


class JWTAuthenticator(VaultAuthenticator):
    """
    JWT/OIDC Vault authenticator.

    Authenticates using JWT tokens or OIDC
    identity provider integration.

    Supported issuers:
    - GitHub Actions (oidc)
    - GitLab CI (oidc)
    - Generic JWT providers

    Usage:
        config = VaultJWTConfig(role="ci-role")
        auth = JWTAuthenticator(config)
        result = await auth.login(client)
    """

    name = "jwt"

    def __init__(self, config: VaultJWTConfig) -> None:
        super().__init__()
        self._config = config
        self._role = config.role
        self._mount = config.mount_point
        self._jwt_token: Optional[str] = config.jwt_token

    def _resolve_jwt_token(self) -> str:
        """
        Resolve the JWT token from various sources.

        Checks environment variables, config,
        and standard CI provider files.

        Returns:
            JWT token string.
        """
        # Explicit config
        if self._jwt_token:
            return self._jwt_token

        # Environment variable
        for env_var in [
            "VAULT_JWT_TOKEN",
            "JWT_TOKEN",
            "GITHUB_OIDC_TOKEN",
            "CI_JOB_JWT",
        ]:
            token = os.environ.get(env_var)
            if token:
                self._jwt_token = token
                return token

        raise VaultAuthenticationError(
            "No JWT token found. Set JWT token via config or environment variable."
        )

    async def login(self, client: VaultClient) -> Dict[str, Any]:
        """
        Authenticate using JWT token.

        Args:
            client: Vault HTTP client.

        Returns:
            Dict with token and metadata.
        """
        if not self._role:
            raise VaultAuthenticationError(
                "JWT auth requires a role name"
            )

        jwt_token = self._resolve_jwt_token()

        path = f"/auth/{self._mount}/login"
        payload = {
            "role": self._role,
            "jwt": jwt_token,
        }

        try:
            result = await client.write(path, payload=payload)
            auth_data = result.get("auth", {})

            self._token = auth_data.get("client_token", "")
            self._logged_in = True
            self._renewable = auth_data.get("renewable", False)

            lease_duration = auth_data.get("lease_duration", 3600)
            self._expires_at = datetime.utcfromtimestamp(
                datetime.utcnow().timestamp() + lease_duration
            )

            self._metadata = {
                "role": self._role,
                "policies": auth_data.get("policies", []),
                "metadata": auth_data.get("metadata", {}),
                "lease_duration": lease_duration,
                "renewable": self._renewable,
            }

            client.set_token(self._token)

            logger.info(
                "JWT authenticated: role=%s, expires=%s",
                self._role,
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
                f"JWT authentication failed: {e}"
            ) from e

    def set_jwt_token(self, token: str) -> None:
        """Set the JWT token for authentication."""
        self._jwt_token = token
        self._config.jwt_token = token

    def get_status(self) -> Dict[str, Any]:
        """Get JWT authenticator status."""
        status = super().get_status()
        status["role"] = self._role
        status["has_jwt_token"] = bool(self._jwt_token)
        return status
