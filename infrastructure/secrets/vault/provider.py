"""
Vault Secrets Provider.

Implements the SecretsProvider interface
using HashiCorp Vault as the backend,
integrating with the existing secrets
platform's manager, registry, and cache.

This is the bridge between the ICYQuant
Secrets Platform and HashiCorp Vault.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models import SecretItem
from ..provider import SecretsProvider
from .authenticator import VaultAuthenticator
from .client import VaultClient
from .config import VaultConfig
from .exceptions import VaultSecretNotFoundError
from .health import VaultHealthChecker
from .kv import KVSecretsEngine
from .lease import LeaseManager
from .namespace import VaultNamespaceManager
from .renew import LeaseRenewer

logger = logging.getLogger(__name__)


class VaultSecretsProvider(SecretsProvider):
    """
    Vault-backed secrets provider.

    Implements the SecretsProvider interface
    using HashiCorp Vault's KV v2 secrets
    engine as the storage backend.

    Features:
    - Full CRUD via Vault HTTP API
    - Automatic authentication (AppRole, Kubernetes, JWT, Token)
    - Lease management with auto-renewal
    - Multi-namespace support
    - High availability failover
    - Health monitoring

    Usage:
        config = VaultConfig(address="http://vault:8200")
        provider = VaultSecretsProvider(config)
        await provider.startup()
        item = await provider.read("database/password")
        await provider.shutdown()
    """

    name = "vault"

    def __init__(
        self,
        config: Optional[VaultConfig] = None,
    ) -> None:
        self._config = config or VaultConfig()
        self._client = VaultClient(self._config)
        self._kv = KVSecretsEngine(self._client, self._config)
        self._lease_manager = LeaseManager()
        self._renewer = LeaseRenewer(self._client, self._lease_manager, self._config.lease)
        self._namespace_mgr = VaultNamespaceManager(self._client, self._config)
        self._health_checker = VaultHealthChecker(
            self._client, self._config, self._lease_manager
        )
        self._authenticator: Optional[VaultAuthenticator] = None
        self._started = False
        self._request_count = 0
        self._cache_hits = 0
        self._cache_misses = 0

    # ── Lifecycle ──

    async def startup(
        self,
        authenticator: Optional[VaultAuthenticator] = None,
    ) -> None:
        """
        Start the Vault provider.

        Args:
            authenticator: Auth method to use.
        """
        await self._client.connect()

        if authenticator:
            self._authenticator = authenticator
            result = await authenticator.login(self._client)
            logger.info(
                "Vault authenticated via %s", authenticator.name
            )
        elif self._config.auth.token and self._config.auth.token.token:
            from .token import TokenAuthenticator
            token_auth = TokenAuthenticator(self._config.auth.token)
            await token_auth.login(self._client)
            self._authenticator = token_auth

        # Start auto-renewal if enabled
        if self._config.auto_renew and self._config.lease.auto_renew:
            await self._renewer.start()

        self._started = True
        logger.info(
            "Vault provider started: %s (namespace: %s)",
            self._config.address,
            self._config.namespace,
        )

    async def shutdown(self) -> None:
        """Shutdown the Vault provider."""
        self._renewer.stop()

        if self._authenticator:
            try:
                await self._authenticator.logout(self._client)
            except Exception as e:
                logger.warning("Auth logout failed: %s", e)

        await self._client.disconnect()
        self._started = False
        logger.info("Vault provider stopped")

    # ── SecretsProvider Interface ──

    async def read(
        self,
        key: str,
        namespace: str = "default",
    ) -> Optional[SecretItem]:
        """
        Read a secret from Vault.

        Args:
            key: Secret key path.
            namespace: Namespace (not used directly,
                       integrated into Vault path).

        Returns:
            SecretItem or None.
        """
        self._request_count += 1

        vault_key = self._build_vault_key(key, namespace)
        value = await self._kv.read(vault_key)

        if value is None:
            return None

        return SecretItem(
            key=key,
            value=str(value),
            provider="vault",
            namespace=namespace,
        )

    async def write(
        self,
        key: str,
        value: str,
        namespace: str = "default",
    ) -> SecretItem:
        """
        Write a secret to Vault.

        Args:
            key: Secret key path.
            value: Secret value.
            namespace: Namespace.

        Returns:
            Created SecretItem.
        """
        self._request_count += 1

        vault_key = self._build_vault_key(key, namespace)
        result = await self._kv.write(vault_key, value)

        return SecretItem(
            key=key,
            value=value,
            provider="vault",
            namespace=namespace,
        )

    async def delete(
        self,
        key: str,
        namespace: str = "default",
    ) -> bool:
        """
        Delete a secret from Vault.

        Args:
            key: Secret key path.
            namespace: Namespace.

        Returns:
            True if deleted.
        """
        self._request_count += 1

        vault_key = self._build_vault_key(key, namespace)
        await self._kv.delete(vault_key)
        return True

    async def list(
        self,
        namespace: str = "default",
    ) -> List[str]:
        """
        List secrets in a namespace.

        Args:
            namespace: Namespace to list.

        Returns:
            List of secret keys.
        """
        self._request_count += 1

        prefix = self._build_namespace_prefix(namespace)
        keys = await self._kv.list(prefix=prefix)

        # Strip namespace prefix from returned keys
        result = []
        for k in keys:
            if prefix:
                result.append(k[len(prefix):] if k.startswith(prefix) else k)
            else:
                result.append(k)

        return result

    async def exists(
        self,
        key: str,
        namespace: str = "default",
    ) -> bool:
        """
        Check if a secret exists.

        Args:
            key: Secret key path.
            namespace: Namespace.

        Returns:
            True if exists.
        """
        vault_key = self._build_vault_key(key, namespace)
        metadata = await self._kv.get_metadata(vault_key)
        return metadata is not None

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.

        Returns:
            Health status dict.
        """
        status = await self._health_checker.check_all()
        return {
            "healthy": status["healthy"],
            "provider": self.name,
            "vault_version": status["checks"].get("vault", {}).get("version", ""),
            "checks": status["checks"],
        }

    # ── Vault-Specific Operations ──

    async def read_metadata(
        self,
        key: str,
        namespace: str = "default",
    ) -> Optional[Dict[str, Any]]:
        """Read secret metadata."""
        vault_key = self._build_vault_key(key, namespace)
        return await self._kv.get_metadata(vault_key)

    async def list_versions(
        self,
        key: str,
        namespace: str = "default",
    ) -> List[int]:
        """List available versions of a secret."""
        vault_key = self._build_vault_key(key, namespace)
        metadata = await self._kv.get_metadata(vault_key)
        if not metadata:
            return []
        versions = metadata.get("versions", {})
        return [int(v) for v in versions.keys()]

    async def delete_version(
        self,
        key: str,
        version: int,
        namespace: str = "default",
    ) -> None:
        """Permanently delete a secret version."""
        vault_key = self._build_vault_key(key, namespace)
        await self._kv.permanent_delete(vault_key, version)

    async def configure_secret(
        self,
        key: str,
        namespace: str = "default",
        max_versions: Optional[int] = None,
        cas_required: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Configure secret metadata."""
        vault_key = self._build_vault_key(key, namespace)
        return await self._kv.configure_metadata(
            vault_key,
            max_versions=max_versions,
            cas_required=cas_required,
        )

    # ── Accessors ──

    @property
    def client(self) -> VaultClient:
        """Get the Vault HTTP client."""
        return self._client

    @property
    def kv(self) -> KVSecretsEngine:
        """Get the KV secrets engine."""
        return self._kv

    @property
    def lease_manager(self) -> LeaseManager:
        """Get the lease manager."""
        return self._lease_manager

    @property
    def renewer(self) -> LeaseRenewer:
        """Get the lease renewer."""
        return self._renewer

    @property
    def namespace_manager(self) -> VaultNamespaceManager:
        """Get the namespace manager."""
        return self._namespace_mgr

    @property
    def health_checker(self) -> VaultHealthChecker:
        """Get the health checker."""
        return self._health_checker

    @property
    def config(self) -> VaultConfig:
        """Get the Vault config."""
        return self._config

    @property
    def is_started(self) -> bool:
        """Check if provider is started."""
        return self._started

    def get_stats(self) -> Dict[str, Any]:
        """Get provider statistics."""
        return {
            "name": self.name,
            "started": self._started,
            "address": self._config.address,
            "namespace": self._config.namespace,
            "request_count": self._request_count,
            "client": self._client.get_stats(),
            "lease_manager": self._lease_manager.get_stats(),
            "renewer": self._renewer.get_stats(),
        }

    # ── Helpers ──

    def _build_vault_key(
        self,
        key: str,
        namespace: str,
    ) -> str:
        """Build full Vault key from key and namespace."""
        if namespace and namespace != "default":
            return f"{namespace}/{key}"
        return key

    def _build_namespace_prefix(self, namespace: str) -> str:
        """Build namespace prefix for listing."""
        if namespace and namespace != "default":
            return f"{namespace}/"
        return ""
