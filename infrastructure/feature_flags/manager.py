"""
Feature flag platform manager.

Provides the unified async entry point for
feature flag operations, orchestrating the
registry, evaluator, cache, and storage
layers to deliver a clean API for applications.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .config import FeatureFlagConfig
from .constants import EvaluationResult, EvaluationStrategy, FeatureFlagType, FlagStatus
from .exceptions import (
    FeatureFlagCacheError,
    FeatureFlagNotFoundError,
    FeatureFlagStorageError,
)
from .models import (
    AuditEntry,
    FeatureContext,
    FeatureEvaluationResult,
    FeatureFlag,
    FeatureRule,
)

logger = logging.getLogger(__name__)


class FeatureFlagManager:
    """
    Unified async entry point for feature flag operations.

    Orchestrates the FeatureRegistry, FeatureEvaluator,
    FeatureFlagCache, and FeatureStorage to provide a
    clean API for applications to query and manage
    feature flags.

    Usage:
        manager = FeatureFlagManager(config)
        await manager.start()
        enabled = await manager.is_enabled("trading.new_risk")
        value = await manager.get("trading.new_risk", context=ctx)
        await manager.shutdown()
    """

    def __init__(
        self,
        config: Optional[FeatureFlagConfig] = None,
        registry: Optional[Any] = None,
        evaluator: Optional[Any] = None,
        cache: Optional[Any] = None,
        storage: Optional[Any] = None,
        audit: Optional[Any] = None,
        metrics: Optional[Any] = None,
    ) -> None:
        """
        Initialize the feature flag manager.

        Args:
            config: Platform configuration.
            registry: FeatureRegistry instance.
            evaluator: FeatureEvaluator instance.
            cache: FeatureFlagCache instance.
            storage: FeatureStorage instance.
            audit: Audit manager instance.
            metrics: Metrics collector instance.
        """
        self._config = config or FeatureFlagConfig()
        self._registry = registry
        self._evaluator = evaluator
        self._cache = cache
        self._storage = storage
        self._audit = audit
        self._metrics = metrics
        self._initialized = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """
        Initialize all components and load flags from storage.

        Creates default components if not provided, loads flags
        from storage into the registry, and sets up cache
        invalidation listeners.
        """
        from .cache import FeatureFlagCache
        from .evaluator import FeatureEvaluator
        from .registry import FeatureRegistry
        from .storage import create_storage

        async with self._lock:
            if self._initialized:
                return

            self._registry = self._registry or FeatureRegistry()
            self._evaluator = self._evaluator or FeatureEvaluator()
            self._cache = self._cache or FeatureFlagCache(
                ttl=self._config.cache_ttl,
                max_size=self._config.cache_max_size,
            )
            self._storage = self._storage or create_storage(
                self._config.storage_backend,
                **(self._config.storage_config or {}),
            )

            await self._storage.start()

            flags = await self._storage.load()
            for flag in flags.values():
                try:
                    await self._registry.register(flag, force=True)
                except Exception as e:
                    logger.warning(
                        "Failed to register flag %s: %s",
                        flag.key, e,
                    )

            self._registry.register_listener(self._on_flag_change)

            self._initialized = True
            logger.info(
                "FeatureFlagManager started with %d flags",
                self._registry.count(),
            )

    async def shutdown(self) -> None:
        """
        Shutdown all components and persist flags to storage.
        """
        async with self._lock:
            if not self._initialized:
                return

            flags = await self._registry.get_all()
            try:
                await self._storage.save(flags)
            except Exception as e:
                logger.error(
                    "Failed to persist flags on shutdown: %s", e,
                )

            await self._storage.shutdown()
            self._initialized = False
            logger.info("FeatureFlagManager shutdown")

    async def is_enabled(
        self,
        key: str,
        context: Optional[FeatureContext] = None,
        default: bool = False,
    ) -> bool:
        """
        Check if a feature flag is enabled.

        Evaluates the flag and returns its boolean value.
        Falls back to the provided default if the flag is
        not found or evaluation fails.

        Args:
            key: Feature flag key.
            context: Evaluation context.
            default: Default value if flag not found.

        Returns:
            True if the feature is enabled.
        """
        result = await self.evaluate(key, context=context)
        if result is None:
            return default
        return bool(result.value)

    async def get(
        self,
        key: str,
        context: Optional[FeatureContext] = None,
    ) -> Optional[FeatureFlag]:
        """
        Get a feature flag definition by key.

        Args:
            key: Feature flag key.
            context: Optional context for audit.

        Returns:
            FeatureFlag or None if not found.
        """
        return self._registry.get(key)

    async def evaluate(
        self,
        key: str,
        context: Optional[FeatureContext] = None,
    ) -> Optional[FeatureEvaluationResult]:
        """
        Evaluate a feature flag and return the result.

        Uses cache when enabled, evaluates through the
        evaluator, and records audit/metrics.

        Args:
            key: Feature flag key.
            context: Evaluation context.

        Returns:
            FeatureEvaluationResult or None if flag not found.
        """
        flag = self._registry.get(key)
        if flag is None:
            logger.debug("Feature flag not found: %s", key)
            return None

        cache_key = self._build_cache_key(key, context)

        if self._config.cache_enabled and self._cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                self._record_metric("cache_hit", key)
                if self._metrics:
                    self._metrics.record_cache_hit(key)
                return cached

        self._record_metric("cache_miss", key)
        if self._metrics:
            self._metrics.record_cache_miss(key)

        result = await self._evaluator.evaluate(flag, context)

        if self._config.cache_enabled and self._cache:
            try:
                await self._cache.put(cache_key, result)
            except FeatureFlagCacheError as e:
                logger.warning(
                    "Cache put failed for %s: %s", key, e,
                )

        self._record_metric(
            "eval", key,
            result_value=result.value,
            result_status=result.result.value,
        )

        if self._audit and self._config.audit_enabled:
            self._audit.record_evaluation(
                flag_key=key,
                result=result,
                context=context,
            )

        return result

    async def create(
        self,
        key: str,
        enabled: bool = True,
        description: str = "",
        flag_type: FeatureFlagType = FeatureFlagType.BOOLEAN,
        strategy: EvaluationStrategy = EvaluationStrategy.STATIC,
        default_value: Any = True,
        tags: Optional[frozenset[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        rules: Optional[List[FeatureRule]] = None,
        owner: str = "system",
    ) -> FeatureFlag:
        """
        Create and register a new feature flag.

        Args:
            key: Unique flag key.
            enabled: Whether the flag is enabled.
            description: Human-readable description.
            flag_type: Type of the flag.
            strategy: Evaluation strategy.
            default_value: Default value.
            tags: Tags for categorization.
            metadata: Additional metadata.
            rules: Targeting rules.
            owner: Flag owner.

        Returns:
            The created FeatureFlag.
        """

        flag = FeatureFlag(
            key=key,
            enabled=enabled,
            description=description,
            flag_type=flag_type,
            strategy=strategy,
            default_value=default_value,
            tags=tags or frozenset(),
            metadata=metadata or {},
            rules=rules or [],
            status=FlagStatus.ACTIVE,
            owner=owner,
        )

        await self._registry.register(flag)
        await self._storage.upsert(flag)

        if self._audit and self._config.audit_enabled:
            await self._audit.record_create(
                flag=flag,
                operator=owner,
            )

        self._record_metric("register", key)
        logger.info("Created feature flag: %s", key)
        return flag

    async def update(
        self,
        key: str,
        **kwargs: Any,
    ) -> FeatureFlag:
        """
        Update an existing feature flag.

        Args:
            key: Flag key to update.
            **kwargs: Attributes to update.

        Returns:
            Updated FeatureFlag.

        Raises:
            FeatureFlagNotFoundError: If flag not found.
        """
        flag = self._registry.get(key)
        if flag is None:
            raise FeatureFlagNotFoundError(key)

        old_enabled = flag.enabled
        new_enabled = kwargs.get("enabled", flag.enabled)

        updated = FeatureFlag(
            key=flag.key,
            enabled=new_enabled,
            description=kwargs.get("description", flag.description),
            flag_type=kwargs.get("flag_type", flag.flag_type),
            strategy=kwargs.get("strategy", flag.strategy),
            default_value=kwargs.get("default_value", flag.default_value),
            tags=kwargs.get("tags", flag.tags),
            metadata=kwargs.get("metadata", flag.metadata),
            rules=kwargs.get("rules", flag.rules),
            status=kwargs.get("status", flag.status),
            created_at=flag.created_at,
            updated_at=flag.updated_at,
            owner=kwargs.get("owner", flag.owner),
            expires_at=kwargs.get("expires_at", flag.expires_at),
        )

        await self._registry.register(updated, force=True)
        await self._storage.upsert(updated)

        if self._cache and self._config.cache_enabled:
            await self._cache.invalidate([key])

        if self._audit and self._config.audit_enabled:
            await self._audit.record_update(
                flag=updated,
                old_enabled=old_enabled,
                new_enabled=new_enabled,
            )

        logger.info("Updated feature flag: %s", key)
        return updated

    async def enable(
        self,
        key: str,
    ) -> FeatureFlag:
        """
        Enable a feature flag.

        Args:
            key: Flag key to enable.

        Returns:
            Updated FeatureFlag.
        """
        old_flag = self._registry.get(key)
        if old_flag is None:
            raise FeatureFlagNotFoundError(key)

        updated = await self._registry.enable(key)
        await self._storage.upsert(updated)

        if self._cache and self._config.cache_enabled:
            await self._cache.invalidate([key])

        if self._audit and self._config.audit_enabled:
            await self._audit.record_state_change(
                flag_key=key,
                old_enabled=old_flag.enabled,
                new_enabled=True,
                operator="system",
            )

        self._record_metric("enable", key)
        return updated

    async def disable(
        self,
        key: str,
    ) -> FeatureFlag:
        """
        Disable a feature flag.

        Args:
            key: Flag key to disable.

        Returns:
            Updated FeatureFlag.
        """
        old_flag = self._registry.get(key)
        if old_flag is None:
            raise FeatureFlagNotFoundError(key)

        updated = await self._registry.disable(key)
        await self._storage.upsert(updated)

        if self._cache and self._config.cache_enabled:
            await self._cache.invalidate([key])

        if self._audit and self._config.audit_enabled:
            await self._audit.record_state_change(
                flag_key=key,
                old_enabled=old_flag.enabled,
                new_enabled=False,
                operator="system",
            )

        self._record_metric("disable", key)
        return updated

    async def delete(
        self,
        key: str,
    ) -> bool:
        """
        Delete a feature flag.

        Args:
            key: Flag key to delete.

        Returns:
            True if deleted.
        """
        flag = self._registry.get(key)
        if flag is None:
            raise FeatureFlagNotFoundError(key)

        await self._registry.unregister(key)
        await self._storage.delete(key)

        if self._config.cache_enabled and self._cache:
            await self._cache.delete(key)

        if self._audit and self._config.audit_enabled:
            await self._audit.record_delete(
                flag_key=key,
                operator="system",
            )

        self._record_metric("delete", key)
        logger.info("Deleted feature flag: %s", key)
        return True

    async def list(
        self,
        tag: Optional[str] = None,
        status: Optional[FlagStatus] = None,
    ) -> List[FeatureFlag]:
        """
        List feature flags with optional filters.

        Args:
            tag: Filter by tag.
            status: Filter by status.

        Returns:
            List of matching flags.
        """
        if tag:
            return self._registry.list_by_tag(tag)
        if status:
            return self._registry.list_by_status(status)
        return list((await self._registry.get_all()).values())

    async def list_active(self) -> List[FeatureFlag]:
        """List all active feature flags."""
        return self._registry.list_active()

    async def sync(self) -> int:
        """
        Sync flags from storage to registry.

        Returns:
            Number of flags synced.
        """
        flags = await self._storage.load()
        count = 0
        for flag in flags.values():
            try:
                await self._registry.register(flag, force=True)
                count += 1
            except Exception as e:
                logger.warning(
                    "Sync failed for flag %s: %s", flag.key, e,
                )

        if self._cache:
            await self._cache.invalidate()

        logger.info("Synced %d flags from storage", count)
        return count

    async def invalidate_cache(
        self,
        keys: Optional[List[str]] = None,
    ) -> int:
        """
        Invalidate cache entries.

        Args:
            keys: Specific keys to invalidate, or None for all.

        Returns:
            Number of entries invalidated.
        """
        if self._cache:
            return await self._cache.invalidate(keys)
        return 0

    def get_registry(self) -> Any:
        """Get the underlying FeatureRegistry."""
        return self._registry

    def get_evaluator(self) -> Any:
        """Get the underlying FeatureEvaluator."""
        return self._evaluator

    def get_cache(self) -> Any:
        """Get the underlying FeatureFlagCache."""
        return self._cache

    def get_config(self) -> FeatureFlagConfig:
        """Get the current configuration."""
        return self._config

    def is_initialized(self) -> bool:
        """Check if the manager is initialized."""
        return self._initialized

    def get_stats(self) -> Dict[str, Any]:
        """Get platform statistics."""
        return {
            "initialized": self._initialized,
            "registry": self._registry.get_stats() if self._registry else {},
            "evaluator": self._evaluator.get_stats() if self._evaluator else {},
            "cache": self._cache.get_stats() if self._cache else {},
            "storage": (
                self._storage.health_check()
                if self._storage else {}
            ),
        }

    def _build_cache_key(
        self,
        key: str,
        context: Optional[FeatureContext],
    ) -> str:
        """Build a cache key from flag key and context."""
        if context and context.target_id:
            return f"{key}:{context.target_id}"
        return key

    def _on_flag_change(
        self,
        action: str,
        flag: FeatureFlag,
    ) -> None:
        """Handle flag change events for cache invalidation."""
        if self._cache and self._config.cache_enabled:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(self._cache.invalidate())
            except RuntimeError:
                pass

    def _record_metric(
        self,
        event: str,
        key: str,
        **kwargs: Any,
    ) -> None:
        """Record an internal metric event."""
        if not self._config.metrics_enabled:
            return

        if self._metrics:
            return

        # Internal metric tracking when no metrics collector
        if not hasattr(self, "_metric_events"):
            self._metric_events: List[Dict[str, Any]] = []
        self._metric_events.append({
            "event": event,
            "key": key,
            "timestamp": asyncio.get_event_loop().time(),
            **kwargs,
        })

    def get_metric_events(self) -> List[Dict[str, Any]]:
        """Get recorded metric events (for testing)."""
        if hasattr(self, "_metric_events"):
            return list(self._metric_events)
        return []