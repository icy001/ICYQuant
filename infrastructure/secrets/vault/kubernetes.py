"""
Vault Kubernetes authenticator.

Implements Kubernetes auth method for
workload identity-based authentication,
suitable for Kubernetes deployments,
Helm charts, and ArgoCD pipelines.

Authentication flow:
1. Pod gets a ServiceAccount token
2. Token is presented to Vault's Kubernetes auth
3. Vault validates token against Kubernetes API
4. Role-based policies are applied
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from .client import VaultClient
from .config import VaultKubernetesConfig
from .exceptions import VaultAuthenticationError
from .authenticator import VaultAuthenticator

logger = logging.getLogger(__name__)


class KubernetesAuthenticator(VaultAuthenticator):
    """
    Kubernetes auth authenticator.

    Uses Kubernetes ServiceAccount tokens
    for workload identity authentication
    with Vault.

    Usage:
        config = VaultKubernetesConfig(role="my-role")
        auth = KubernetesAuthenticator(config)
        result = await auth.login(client)
    """

    name = "kubernetes"

    def __init__(self, config: VaultKubernetesConfig) -> None:
        super().__init__()
        self._config = config
        self._role = config.role
        self._mount = config.mount_point
        self._service_account_token: Optional[str] = None

    def _load_service_account_token(self) -> str:
        """
        Load the Kubernetes ServiceAccount token.

        Returns:
            Token string.
        """
        # Check environment variable first
        token = os.environ.get("VAULT_K8S_TOKEN")
        if token:
            return token

        # Read from mounted volume
        token_path = self._config.service_account_token_path
        try:
            with open(token_path, "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            raise VaultAuthenticationError(
                f"Kubernetes ServiceAccount token not found at: {token_path}"
            )
        except IOError as e:
            raise VaultAuthenticationError(
                f"Cannot read Kubernetes token: {e}"
            ) from e

    async def login(self, client: VaultClient) -> Dict[str, Any]:
        """
        Authenticate using Kubernetes ServiceAccount token.

        Args:
            client: Vault HTTP client.

        Returns:
            Dict with token and metadata.
        """
        if not self._role:
            raise VaultAuthenticationError(
                "Kubernetes auth requires a role name"
            )

        # Load ServiceAccount token
        sa_token = self._load_service_account_token()
        self._service_account_token = sa_token

        path = f"/auth/{self._mount}/login"
        payload = {
            "role": self._role,
            "jwt": sa_token,
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
                "role": self._role,
                "policies": auth_data.get("policies", []),
                "service_account": auth_data.get("metadata", {}).get(
                    "service_account_name", ""
                ),
                "namespace": auth_data.get("metadata", {}).get(
                    "service_account_namespace", ""
                ),
                "lease_duration": lease_duration,
            }

            client.set_token(self._token)

            logger.info(
                "Kubernetes authenticated: role=%s, sa=%s",
                self._role,
                self._metadata.get("service_account", "?"),
            )

            return {
                "token": self._token,
                "renewable": self._renewable,
                "expires_at": self._expires_at.isoformat() if self._expires_at else None,
                "metadata": self._metadata,
            }

        except Exception as e:
            raise VaultAuthenticationError(
                f"Kubernetes authentication failed: {e}"
            ) from e

    def get_status(self) -> Dict[str, Any]:
        """Get Kubernetes authenticator status."""
        status = super().get_status()
        status["role"] = self._role
        status["has_sa_token"] = bool(self._service_account_token)
        return status
