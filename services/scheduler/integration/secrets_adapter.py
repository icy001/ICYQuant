"""Secrets Adapter — integrates the Scheduler with Secret Management.

The :class:`SecretsAdapter` provides secure access to credentials,
API keys, and sensitive configuration needed by scheduled jobs:
* Secret retrieval and caching
* Rotation-aware secret access
* Provider abstraction (Vault, K8s, AWS, env)

Architecture::

    Secret Store ──→ SecretsAdapter ──→ SchedulerEngine
                         │
                 Retrieve / Rotate / Cache
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SecretProvider(enum.Enum):
    """Secret management providers."""

    ENVIRONMENT = "environment"
    VAULT = "vault"
    KUBERNETES = "kubernetes"
    AWS_SECRETS = "aws_secrets"
    AZURE_KEYVAULT = "azure_keyvault"
    GCP_SECRETS = "gcp_secrets"


class SecretsAdapter:
    """Adapter for secret management integration.

    Responsibilities:
    * Retrieve secrets for scheduled job execution
    * Cache secrets with TTL to reduce provider calls
    * Handle secret rotation transparently
    * Support multiple secret providers

    Usage::

        adapter = SecretsAdapter(provider=SecretProvider.VAULT)
        await adapter.connect()
        api_key = await adapter.get_secret("trading-api-key")
    """

    def __init__(self, provider: SecretProvider = SecretProvider.ENVIRONMENT) -> None:
        self._provider = provider
        self._lock = threading.Lock()
        self._connected = False
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 300.0  # 5 minutes
        self._fetch_count: int = 0
        self._cache_hits: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def provider(self) -> SecretProvider:
        return self._provider

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def fetch_count(self) -> int:
        return self._fetch_count

    @property
    def cache_hits(self) -> int:
        return self._cache_hits

    @property
    def cached_secrets(self) -> int:
        return len(self._cache)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the secret management provider."""
        logger.info("SecretsAdapter: connecting to %s", self._provider.value)
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect and clear secret cache."""
        self._connected = False
        self._cache.clear()
        logger.info("SecretsAdapter: disconnected, cache cleared")

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize secret state."""
        return {
            "provider": self._provider.value,
            "cached_secrets": len(self._cache),
            "fetch_count": self._fetch_count,
            "cache_hits": self._cache_hits,
        }

    # ------------------------------------------------------------------
    # Secret Access
    # ------------------------------------------------------------------

    async def get_secret(self, key: str, default: Any = None) -> Any:
        """Retrieve a secret by key.

        Checks cache first; fetches from provider on cache miss.
        """
        # Check cache
        cached = self._cache.get(key)
        if cached:
            age = (datetime.now(timezone.utc) - cached["fetched_at"]).total_seconds()
            if age < self._cache_ttl:
                self._cache_hits += 1
                return cached["value"]

        # Fetch from provider
        self._fetch_count += 1
        value = await self._fetch_secret(key)

        if value is not None:
            self._cache[key] = {
                "value": value,
                "fetched_at": datetime.now(timezone.utc),
            }
            return value

        return default

    async def get_secrets(self, keys: List[str]) -> Dict[str, Any]:
        """Batch retrieve multiple secrets."""
        results = {}
        for key in keys:
            results[key] = await self.get_secret(key)
        return results

    async def invalidate(self, key: str) -> None:
        """Invalidate a cached secret (force re-fetch on next access)."""
        self._cache.pop(key, None)
        logger.debug("SecretsAdapter: invalidated %s", key)

    async def invalidate_all(self) -> None:
        """Invalidate all cached secrets."""
        self._cache.clear()
        logger.info("SecretsAdapter: all secrets invalidated")

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _fetch_secret(self, key: str) -> Optional[Any]:
        """Fetch a secret from the configured provider."""
        # In production, this calls Vault/K8s/AWS/etc.
        import os
        value = os.environ.get(key)
        if value:
            logger.debug("SecretsAdapter: fetched %s from environment", key)
        return value
