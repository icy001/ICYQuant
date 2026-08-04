"""
Feature flag platform service layer.

Provides a high-level service that integrates
the manager, resolver, audit, metrics, and
health components. Serves as the main
integration point for application code.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .audit import AuditManager
from .cache import FeatureFlagCache
from .config import FeatureFlagConfig
from .constants import (
    EvaluationStrategy,
    FeatureFlagType,
    FlagStatus,
    OperatorAction,
)
from .evaluator import FeatureEvaluator
from .exceptions import (
    FeatureFlagError,
    FeatureFlagNotFoundError,
    FeatureFlagValidationError,
)
from .health import FeatureFlagHealth
from .manager import FeatureFlagManager
from .metrics import FeatureFlagMetrics
from .models import (
    FeatureContext,
    FeatureEvaluationResult,
    FeatureFlag,
    FeatureRule,
)
from .registry import FeatureRegistry
from .resolver import FeatureResolver
from .storage import create_storage
from .validator import FeatureFlagValidator
from .utils import generate_id, generate_trace_id

logger = logging.getLogger(__name__)


class FeatureFlagService:
    """
    High-level feature flag service.

    Integrates all platform components into a
    single service that applications can use.
    Provides both simple boolean queries and
    advanced evaluation with context.

    Features:
        - Simple enabled/disabled checks
        - Context-aware evaluation
        - Flag lifecycle management
        - Audit trail for all operations
        - Prometheus metrics
        - Health check integration

    Usage:
        service = FeatureFlagService(config)
        await service.start()

        # Simple check
        if await service.is_enabled("trading.new_risk"):
            ...

        # Context-aware
        ctx = FeatureContext(target_id="acc_123", target_type="account")
        result = await service.evaluate("trading.new_risk", ctx)
    """

    def __init__(
        self,
        config: Optional[FeatureFlagConfig] = None,
    ) -> None:
        """
        Initialize the feature flag service.

        Args:
            config: Platform configuration.
        """
        self._config = config or FeatureFlagConfig()
        self._initialized = False

        # Initialize core components
        self._validator = FeatureFlagValidator(
            max_rules_per_flag=self._config.max_rules_per_flag,
        )
        self._audit = AuditManager(
            max_entries=self._config.audit_max_entries,
        )
        self._metrics = FeatureFlagMetrics()
        self._storage = create_storage(
            self._config.storage_backend,
            **(self._config.storage_config or {}),
        )
        self._cache = FeatureFlagCache(
            ttl=self._config.cache_ttl,
            max_size=self._config.cache_max_size,
        )
        self._evaluator = FeatureEvaluator()
        self._registry = FeatureRegistry()
        self._manager = FeatureFlagManager(
            config=self._config,
            registry=self._registry,
            evaluator=self._evaluator,
            cache=self._cache,
            storage=self._storage,
            audit=self._audit,
            metrics=self._metrics,
        )
        self._resolver = FeatureResolver(
            manager=self._manager,
            registry=self._registry,
            evaluator=self._evaluator,
            cache=self._cache,
        )
        self._health = FeatureFlagHealth(
            manager=self._manager,
            registry=self._registry,
            evaluator=self._evaluator,
            cache=self._cache,
            storage=self._storage,
            audit=self._audit,
            metrics=self._metrics,
        )

    async def start(self) -> None:
        """
        Initialize the service and load flags from storage.
        """
        await self._manager.start()
        self._initialized = True
        logger.info("FeatureFlagService started")

    async def shutdown(self) -> None:
        """
        Shutdown the service and persist flags.
        """
        await self._manager.shutdown()
        self._initialized = False
        logger.info("FeatureFlagService shutdown")

    async def is_enabled(
        self,
        key: str,
        context: Optional[FeatureContext] = None,
        default: bool = False,
    ) -> bool:
        """
        Check if a feature flag is enabled.

        Args:
            key: Feature flag key.
            context: Evaluation context.
            default: Default value if flag not found.

        Returns:
            True if the feature is enabled.
        """
        if not self._config.enabled:
            return default

        result = await self._resolver.resolve_bool(key, context, default)
        return result

    async def evaluate(
        self,
        key: str,
        context: Optional[FeatureContext] = None,
    ) -> FeatureEvaluationResult:
        """
        Evaluate a feature flag and return detailed result.

        Args:
            key: Feature flag key.
            context: Evaluation context.

        Returns:
            FeatureEvaluationResult with details.
        """
        return await self._resolver.resolve(key, context)

    async def get_value(
        self,
        key: str,
        context: Optional[FeatureContext] = None,
        default: Any = None,
    ) -> Any:
        """
        Get a feature flag's value.

        Args:
            key: Feature flag key.
            context: Evaluation context.
            default: Default value if resolution fails.

        Returns:
            Flag value.
        """
        return await self._resolver.resolve_variant(key, context, default)

    async def create_flag(
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

        Validates the flag before registration.

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

        Raises:
            FeatureFlagValidationError: If validation fails.
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

        # Validate
        errors = self._validator.validate_flag(flag)
        if errors:
            raise FeatureFlagValidationError(
                message=f"Validation failed for flag '{key}'",
                errors=errors,
            )

        # Create via manager
        created = await self._manager.create(
            key=key,
            enabled=enabled,
            description=description,
            flag_type=flag_type,
            strategy=strategy,
            default_value=default_value,
            tags=tags,
            metadata=metadata,
            rules=rules,
            owner=owner,
        )

        self._metrics.record_register(key)
        return created

    async def update_flag(
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
        """
        updated = await self._manager.update(key, **kwargs)
        self._metrics.record_update(key)
        return updated

    async def enable_flag(
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
        return await self._manager.enable(key)

    async def disable_flag(
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
        return await self._manager.disable(key)

    async def delete_flag(
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
        result = await self._manager.delete(key)
        if result:
            self._metrics.record_delete(key)
        return result

    async def list_flags(
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
        return await self._manager.list(tag=tag, status=status)

    async def get_flag(
        self,
        key: str,
    ) -> Optional[FeatureFlag]:
        """
        Get a feature flag definition.

        Args:
            key: Flag key.

        Returns:
            FeatureFlag or None.
        """
        return await self._manager.get(key)

    async def sync(self) -> int:
        """
        Sync flags from storage.

        Returns:
            Number of flags synced.
        """
        return await self._manager.sync()

    async def check_health(self) -> Dict[str, Any]:
        """
        Run a comprehensive health check.

        Returns:
            Health status dictionary.
        """
        return await self._health.check()

    def is_ready(self) -> bool:
        """
        Check if the platform is ready.

        Returns:
            True if all critical components are healthy.
        """
        return self._health.is_ready()

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """
        Get current metrics snapshot.

        Returns:
            Metrics dictionary.
        """
        return self._metrics.snapshot()

    def get_metrics_exporter(self) -> Any:
        """Get Prometheus metrics exporter."""
        from .metrics import FeatureFlagPrometheusExporter
        return FeatureFlagPrometheusExporter(self._metrics)

    async def query_audit(
        self,
        flag_key: Optional[str] = None,
        action: Optional[OperatorAction] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query audit entries.

        Args:
            flag_key: Filter by flag key.
            action: Filter by action.
            limit: Max entries to return.

        Returns:
            List of audit entry dictionaries.
        """
        entries = await self._audit.query(
            flag_key=flag_key,
            action=action,
            limit=limit,
        )
        return [
            self._audit._entry_to_dict(e) for e in entries
        ]

    def get_config(self) -> FeatureFlagConfig:
        """Get current configuration."""
        return self._config

    def get_manager(self) -> FeatureFlagManager:
        """Get the underlying FeatureFlagManager."""
        return self._manager

    def get_registry(self) -> FeatureRegistry:
        """Get the underlying FeatureRegistry."""
        return self._registry

    def get_evaluator(self) -> FeatureEvaluator:
        """Get the underlying FeatureEvaluator."""
        return self._evaluator

    def get_cache(self) -> FeatureFlagCache:
        """Get the underlying FeatureFlagCache."""
        return self._cache

    def get_storage(self) -> Any:
        """Get the underlying FeatureStorage."""
        return self._storage

    def get_audit(self) -> AuditManager:
        """Get the underlying AuditManager."""
        return self._audit

    def get_metrics(self) -> FeatureFlagMetrics:
        """Get the underlying FeatureFlagMetrics."""
        return self._metrics

    def get_validator(self) -> FeatureFlagValidator:
        """Get the underlying FeatureFlagValidator."""
        return self._validator

    def is_initialized(self) -> bool:
        """Check if the service is initialized."""
        return self._initialized

    async def export_flags(
        self,
    ) -> Dict[str, Any]:
        """
        Export all flags for backup or migration.

        Returns:
            Dictionary with flag definitions and metadata.
        """
        flags = await self._manager.list()
        return {
            "exported_at": datetime.utcnow().isoformat(),
            "version": generate_id(),
            "flags": [
                {
                    "key": f.key,
                    "enabled": f.enabled,
                    "description": f.description,
                    "flag_type": f.flag_type.value,
                    "strategy": f.strategy.value,
                    "default_value": str(f.default_value),
                    "tags": list(f.tags),
                    "metadata": f.metadata,
                    "rules": [
                        {
                            "rule_id": r.rule_id,
                            "priority": r.priority,
                            "condition": r.condition,
                            "value": str(r.value),
                        }
                        for r in f.rules
                    ],
                    "status": f.status.value,
                    "owner": f.owner,
                    "created_at": f.created_at.isoformat(),
                    "updated_at": f.updated_at.isoformat(),
                }
                for f in flags
            ],
            "count": len(flags),
        }

    def get_service_stats(self) -> Dict[str, Any]:
        """Get comprehensive service statistics."""
        return {
            "initialized": self._initialized,
            "config": {
                "enabled": self._config.enabled,
                "cache_enabled": self._config.cache_enabled,
                "storage_backend": self._config.storage_backend.value,
            },
            "registry": self._registry.get_stats(),
            "evaluator": self._evaluator.get_stats(),
            "cache": self._cache.get_stats(),
            "audit": self._audit.get_stats(),
            "metrics": self._metrics.snapshot(),
        }