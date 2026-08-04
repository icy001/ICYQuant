"""
Secrets manager.

Unified entry point for the secrets
platform, coordinating the registry,
provider, resolver, cache, and policy
components for all secret operations.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .cache import SecretsCache
from .config import SecretsConfig
from .constants import AuditAction
from .exceptions import (
    SecretAccessDeniedError,
    SecretNotFoundError,
    SecretProviderError,
    SecretValidationError,
)
from .models import SecretItem, SecretMetadata
from .provider import ProviderFactory, SecretsProvider
from .registry import SecretsRegistry
from .resolver import SecretResolver

logger = logging.getLogger(__name__)


class SecretsManager:
    """
    Unified secrets manager.

    Provides the primary API for all secrets
    operations, coordinating the registry,
    provider, cache, resolver, and policy
    components.

    Usage:
        manager = SecretsManager()
        await manager.startup()
        value = await manager.get("db/password")
    """

    def __init__(
        self,
        config: Optional[SecretsConfig] = None,
        provider: Optional[SecretsProvider] = None,
        registry: Optional[SecretsRegistry] = None,
        cache: Optional[SecretsCache] = None,
    ) -> None:
        """
        Initialize secrets manager.

        Args:
            config: Platform configuration.
            provider: Pre-configured provider.
            registry: Pre-configured registry.
            cache: Pre-configured cache.
        """
        self._config = config or SecretsConfig()
        self._factory = ProviderFactory()
        self._registry = registry or SecretsRegistry()
        self._cache = cache or SecretsCache(
            ttl=self._config.cache_ttl,
            max_size=self._config.cache_max_size,
        )
        self._provider = provider
        self._resolver = SecretResolver(
            provider=self._provider,
            registry=self._registry,
            cache=self._cache,
        )
        self._started = False
        self._startup_time: Optional[datetime] = None
        self._audit: Any = None  # SecretsAudit (lazy init)
        self._policy: Any = None  # SecretAccessPolicy (lazy init)
        self._permissions: Any = None  # PermissionModel (lazy init)
        self._metrics: Any = None  # SecretsMetrics (lazy init)

    # ── Lifecycle ──

    async def startup(self) -> Dict[str, Any]:
        """
        Start the secrets manager.

        Initializes the provider and verifies
        connectivity.

        Returns:
            Startup result dict.
        """
        if self._started:
            return {"success": True, "message": "Already started"}

        try:
            # Initialize provider
            if not self._provider:
                self._provider = self._factory.create(self._config.provider)

            # Set resolver references
            self._resolver.set_provider(self._provider)
            self._resolver.set_registry(self._registry)
            self._resolver.set_cache(self._cache)

            self._started = True
            self._startup_time = datetime.utcnow()

            logger.info(
                "Secrets manager started with provider: %s",
                self._config.provider,
            )

            return {
                "success": True,
                "provider": self._config.provider,
                "started_at": self._startup_time.isoformat() + "Z",
            }
        except Exception as e:
            logger.error("Failed to start secrets manager: %s", e)
            return {"success": False, "error": str(e)}

    async def shutdown(self) -> Dict[str, Any]:
        """
        Shutdown the secrets manager.

        Returns:
            Shutdown result dict.
        """
        if not self._started:
            return {"success": True, "message": "Not started"}

        self._started = False
        self._cache.clear()

        logger.info("Secrets manager shutdown")

        return {"success": True}

    @property
    def is_started(self) -> bool:
        """Check if manager is started."""
        return self._started

    @property
    def config(self) -> SecretsConfig:
        """Get configuration."""
        return self._config

    @property
    def registry(self) -> SecretsRegistry:
        """Get secrets registry."""
        return self._registry

    @property
    def cache(self) -> SecretsCache:
        """Get secrets cache."""
        return self._cache

    @property
    def provider(self) -> Optional[SecretsProvider]:
        """Get current provider."""
        return self._provider

    @property
    def resolver(self) -> SecretResolver:
        """Get secret resolver."""
        return self._resolver

    # ── Core Operations ──

    async def get(
        self,
        key: str,
        namespace: str = "default",
        use_cache: bool = True,
    ) -> Optional[str]:
        """
        Get a secret value.

        Args:
            key: The secret key.
            namespace: Namespace.
            use_cache: Whether to check cache.

        Returns:
            Secret value or None.

        Raises:
            SecretNotFoundError: If key not found and not cached.
        """
        if not self._started:
            await self.startup()

        start = time.time()

        # Check cache
        if use_cache and self._config.cache_enabled:
            cached = self._cache.get(key, namespace)
            if cached is not None:
                elapsed_ms = (time.time() - start) * 1000
                self._record_access(key, namespace, True, True, elapsed_ms)
                return cached

        # Try registry first (has local copies)
        try:
            item = self._registry.get(key, namespace)
            if item.is_expired:
                raise SecretNotFoundError(key, namespace)

            # Cache the value
            if use_cache and self._config.cache_enabled:
                self._cache.put(key, item.value, namespace)

            elapsed_ms = (time.time() - start) * 1000
            self._record_access(key, namespace, True, False, elapsed_ms)
            return item.value
        except SecretNotFoundError:
            pass

        # Try provider
        if self._provider:
            try:
                item = await self._provider.read(key, namespace)
                if item and not item.is_expired:
                    # Register in registry
                    self._registry.register(item)

                    # Cache
                    if use_cache and self._config.cache_enabled:
                        self._cache.put(key, item.value, namespace)

                    elapsed_ms = (time.time() - start) * 1000
                    self._record_access(key, namespace, True, False, elapsed_ms)
                    return item.value
            except Exception as e:
                logger.warning("Provider read failed for %s: %s", key, e)

        # Not found anywhere
        elapsed_ms = (time.time() - start) * 1000
        self._record_access(key, namespace, False, False, elapsed_ms)
        raise SecretNotFoundError(key, namespace)

    async def get_metadata(
        self,
        key: str,
        namespace: str = "default",
    ) -> Optional[SecretMetadata]:
        """
        Get secret metadata without exposing value.

        Args:
            key: The secret key.
            namespace: Namespace.

        Returns:
            SecretMetadata or None.
        """
        return self._registry.get_metadata(key, namespace)

    async def set(
        self,
        key: str,
        value: str,
        namespace: str = "default",
        **kwargs: Any,
    ) -> SecretItem:
        """
        Set (create or update) a secret.

        Args:
            key: The secret key.
            value: The secret value.
            namespace: Namespace.
            **kwargs: Additional SecretItem fields.

        Returns:
            Created/updated SecretItem.
        """
        if not self._started:
            await self.startup()

        # Validate size
        if len(value) > self._config.max_secret_size:
            raise SecretValidationError(
                key,
                [f"Value exceeds max size ({len(value)} > {self._config.max_secret_size})"],
            )

        # Write to provider
        if self._provider:
            try:
                item = await self._provider.write(
                    key, value, namespace, **kwargs
                )
            except Exception as e:
                raise SecretProviderError(
                    self._config.provider, "write", str(e)
                )
        else:
            item = SecretItem(
                key=key,
                value=value,
                provider=self._config.provider,
                namespace=namespace,
                **kwargs,
            )

        # Register in registry
        self._registry.register(item)

        # Invalidate cache
        self._cache.invalidate(key, namespace)

        # Audit
        self._record_change(key, "create" if item.version == 1 else "update")

        return item

    async def update(
        self,
        key: str,
        value: str,
        namespace: str = "default",
        **kwargs: Any,
    ) -> SecretItem:
        """
        Update an existing secret.

        Args:
            key: The secret key.
            value: New value.
            namespace: Namespace.
            **kwargs: Additional SecretItem fields.

        Returns:
            Updated SecretItem.
        """
        if not self._started:
            await self.startup()

        # Validate size
        if len(value) > self._config.max_secret_size:
            raise SecretValidationError(
                key,
                [f"Value exceeds max size ({len(value)} > {self._config.max_secret_size})"],
            )

        # Update via provider
        if self._provider:
            try:
                item = await self._provider.update(
                    key, value, namespace, **kwargs
                )
            except SecretNotFoundError:
                raise
            except Exception as e:
                raise SecretProviderError(
                    self._config.provider, "update", str(e)
                )
        else:
            item = self._registry.update(key, value, namespace, **kwargs)

        # Invalidate cache
        self._cache.invalidate(key, namespace)

        # Audit
        self._record_change(key, "update")

        return item

    async def delete(
        self,
        key: str,
        namespace: str = "default",
    ) -> bool:
        """
        Delete a secret.

        Args:
            key: The secret key.
            namespace: Namespace.

        Returns:
            True if deleted.
        """
        if not self._started:
            await self.startup()

        # Delete from provider
        if self._provider:
            try:
                await self._provider.delete(key, namespace)
            except Exception:
                pass

        # Delete from registry
        result = self._registry.delete(key, namespace)

        # Invalidate cache
        self._cache.invalidate(key, namespace)

        if result:
            self._record_change(key, "delete")

        return result

    async def refresh(
        self,
        key: str,
        namespace: str = "default",
    ) -> Optional[str]:
        """
        Refresh a secret by invalidating cache and re-reading.

        Args:
            key: The secret key.
            namespace: Namespace.

        Returns:
            Fresh secret value.
        """
        # Invalidate cache
        self._cache.invalidate(key, namespace)

        # Remove from registry to force fresh read
        # Don't delete - just clear the cached value
        # We need to force a provider read
        metadata = self._registry.get_metadata(key, namespace)
        if not metadata:
            return None

        # Get fresh value
        value = await self.get(key, namespace, use_cache=False)

        self._record_change(key, "refresh")
        return value

    async def rotate(
        self,
        key: str,
        new_value: Optional[str] = None,
        namespace: str = "default",
    ) -> SecretItem:
        """
        Rotate a secret with a new value.

        Args:
            key: The secret key.
            new_value: New value (auto-generated if None).
            namespace: Namespace.

        Returns:
            Rotated SecretItem.
        """
        if new_value is None:
            import secrets
            new_value = secrets.token_urlsafe(32)

        # Update the secret
        item = await self.update(key, new_value, namespace)

        # Mark as rotated
        self._record_change(key, "rotate")

        return item

    # ── Listing ──

    async def list_secrets(
        self,
        namespace: str = "default",
    ) -> List[str]:
        """
        List all secret keys.

        Args:
            namespace: Namespace.

        Returns:
            List of secret keys.
        """
        # Get from registry
        keys = self._registry.list_secrets(namespace)

        # Also get from provider
        if self._provider:
            try:
                provider_keys = await self._provider.list(namespace)
                # Merge (registry takes precedence)
                for key in provider_keys:
                    if key not in keys:
                        keys.append(key)
            except Exception:
                pass

        return keys

    async def list_metadata(
        self,
        namespace: str = "default",
    ) -> List[SecretMetadata]:
        """
        List all secret metadata.

        Args:
            namespace: Namespace.

        Returns:
            List of SecretMetadata.
        """
        return self._registry.list_metadata(namespace)

    async def list_namespaces(self) -> List[str]:
        """List all namespaces."""
        return self._registry.list_namespaces()

    async def exists(
        self,
        key: str,
        namespace: str = "default",
    ) -> bool:
        """Check if a secret exists."""
        if self._registry.exists(key, namespace):
            return True
        if self._provider:
            try:
                return await self._provider.exists(key, namespace)
            except Exception:
                return False
        return False

    # ── Resolution ──

    def resolve(
        self,
        reference: str,
    ) -> Optional[str]:
        """
        Resolve a ${secret:...} reference (sync).

        Args:
            reference: Reference string.

        Returns:
            Resolved value or None.
        """
        return self._resolver.resolve(reference)

    async def async_resolve(
        self,
        reference: str,
    ) -> Optional[str]:
        """
        Resolve a ${secret:...} reference (async).

        Args:
            reference: Reference string.

        Returns:
            Resolved value or None.
        """
        return await self._resolver.async_resolve(reference)

    def resolve_in_text(
        self,
        text: str,
    ) -> str:
        """
        Resolve all references in text (sync).

        Args:
            text: Text with references.

        Returns:
            Resolved text.
        """
        return self._resolver.resolve_in_text(text)

    async def async_resolve_in_text(
        self,
        text: str,
    ) -> str:
        """
        Resolve all references in text (async).

        Args:
            text: Text with references.

        Returns:
            Resolved text.
        """
        return await self._resolver.async_resolve_in_text(text)

    # ── Cache Management ──

    def clear_cache(
        self,
        namespace: Optional[str] = None,
    ) -> None:
        """
        Clear the secrets cache.

        Args:
            namespace: Optional namespace to clear.
        """
        if namespace:
            self._cache.clear_namespace(namespace)
        else:
            self._cache.clear()

    def cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self._cache.get_stats()

    # ── Status ──

    async def get_status(self) -> Dict[str, Any]:
        """Get manager status."""
        registry_stats = self._registry.get_stats()
        cache_stats = self._cache.get_stats()

        return {
            "started": self._started,
            "startup_time": (
                self._startup_time.isoformat() + "Z"
                if self._startup_time
                else None
            ),
            "provider": self._config.provider,
            "total_secrets": registry_stats["total_secrets"],
            "namespaces": registry_stats["namespaces"],
            "cache": cache_stats,
            "resolver": self._resolver.get_stats(),
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Check platform health.

        Returns:
            Health status dict.
        """
        result = {
            "healthy": True,
            "provider": True,
            "cache": True,
            "resolver": True,
            "registry": True,
        }

        # Check provider
        if self._provider:
            try:
                provider_health = await self._provider.health_check()
                result["provider"] = provider_health.get("healthy", True)
            except Exception:
                result["provider"] = False
                result["healthy"] = False

        # Check registry
        try:
            result["registry"] = self._registry.total_count() >= 0
        except Exception:
            result["registry"] = False
            result["healthy"] = False

        # Check cache
        try:
            result["cache"] = self._cache.size() >= 0
        except Exception:
            result["cache"] = False
            result["healthy"] = False

        return result

    # ── Internal ──

    def _record_access(
        self,
        key: str,
        namespace: str,
        allowed: bool,
        cache_hit: bool,
        latency_ms: float,
    ) -> None:
        """Record a secret access for audit/metrics."""
        if self._config.audit_enabled and self._audit:
            self._audit.log_access(
                key=key,
                namespace=namespace,
                allowed=allowed,
                cache_hit=cache_hit,
                latency_ms=latency_ms,
            )

    def _record_change(
        self,
        key: str,
        action: str,
    ) -> None:
        """Record a secret change for audit/metrics."""
        if self._config.audit_enabled and self._audit:
            self._audit.log_change(
                key=key,
                action=action,
            )

    def set_audit(self, audit: Any) -> None:
        """Set the audit component."""
        self._audit = audit

    def set_policy(self, policy: Any) -> None:
        """Set the access policy component."""
        self._policy = policy

    def set_permissions(self, permissions: Any) -> None:
        """Set the permissions component."""
        self._permissions = permissions

    def set_metrics(self, metrics: Any) -> None:
        """Set the metrics component."""
        self._metrics = metrics
