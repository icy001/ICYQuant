"""
Feature flag platform resolution pipeline.

Implements the resolution flow:
Application → Manager → Registry → Evaluator → Cache → Result

Provides a layered resolution system with
fallback support and cache integration.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .constants import EvaluationResult
from .exceptions import FeatureFlagError, FeatureFlagNotFoundError
from .models import FeatureContext, FeatureEvaluationResult, FeatureFlag

logger = logging.getLogger(__name__)


class FeatureResolver:
    """
    Multi-layer resolution pipeline for feature flags.

    Resolves feature flag values through a layered
    pipeline: Registry → Cache → Evaluator → Result.
    Supports fallback to defaults and error handling
    at each layer.

    Pipeline:
        Application
              ↓
        FeatureFlagManager
              ↓
        FeatureRegistry (get flag definition)
              ↓
        FeatureFlagCache (check cache)
              ↓
        FeatureEvaluator (evaluate rules)
              ↓
        FeatureFlagCache (store result)
              ↓
            Result

    Usage:
        resolver = FeatureResolver(manager)
        result = await resolver.resolve("trading.new_risk", context)
    """

    def __init__(
        self,
        manager: Any = None,
        registry: Any = None,
        evaluator: Any = None,
        cache: Any = None,
    ) -> None:
        """
        Initialize the resolver.

        Args:
            manager: FeatureFlagManager instance (optional).
            registry: FeatureRegistry instance.
            evaluator: FeatureEvaluator instance.
            cache: FeatureFlagCache instance.
        """
        self._manager = manager
        self._registry = registry
        self._evaluator = evaluator
        self._cache = cache
        self._resolution_count = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._error_count = 0
        self._lock = asyncio.Lock()

    async def resolve(
        self,
        key: str,
        context: Optional[FeatureContext] = None,
        use_cache: bool = True,
    ) -> FeatureEvaluationResult:
        """
        Resolve a feature flag value through the pipeline.

        Args:
            key: Feature flag key to resolve.
            context: Evaluation context.
            use_cache: Whether to use caching.

        Returns:
            FeatureEvaluationResult with the resolved value.

        Raises:
            FeatureFlagNotFoundError: If flag not found and
                no default can be determined.
        """
        self._resolution_count += 1
        cache_key = self._build_cache_key(key, context)

        # Layer 1: Cache lookup
        if use_cache and self._cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                self._cache_hits += 1
                return cached

        self._cache_misses += 1

        # Layer 2: Registry lookup
        flag = self._get_flag(key)
        if flag is None:
            raise FeatureFlagNotFoundError(key)

        # Layer 3: Evaluation
        try:
            result = await self._evaluator.evaluate(flag, context)
        except Exception as e:
            self._error_count += 1
            logger.error(
                "Resolution failed for flag %s: %s",
                key, e,
            )
            result = FeatureEvaluationResult(
                key=key,
                value=flag.default_value,
                enabled=flag.enabled,
                result=EvaluationResult.ERROR,
                reason=str(e),
            )

        # Layer 4: Cache store
        if use_cache and self._cache:
            try:
                await self._cache.put(cache_key, result)
            except Exception as e:
                logger.warning(
                    "Cache store failed for %s: %s", key, e,
                )

        return result

    async def resolve_bool(
        self,
        key: str,
        context: Optional[FeatureContext] = None,
        default: bool = False,
    ) -> bool:
        """
        Resolve a feature flag to a boolean value.

        Args:
            key: Feature flag key.
            context: Evaluation context.
            default: Default value if resolution fails.

        Returns:
            Boolean flag value.
        """
        try:
            result = await self.resolve(key, context)
            return bool(result.value)
        except FeatureFlagNotFoundError:
            logger.debug("Flag not found, using default: %s", key)
            return default
        except Exception as e:
            logger.warning(
                "Resolution error for flag %s: %s. Using default.",
                key, e,
            )
            return default

    async def resolve_variant(
        self,
        key: str,
        context: Optional[FeatureContext] = None,
        default: Any = None,
    ) -> Any:
        """
        Resolve a feature flag to a variant value.

        Args:
            key: Feature flag key.
            context: Evaluation context.
            default: Default value if resolution fails.

        Returns:
            Variant flag value.
        """
        try:
            result = await self.resolve(key, context)
            return result.value
        except FeatureFlagNotFoundError:
            logger.debug("Flag not found, using default: %s", key)
            return default
        except Exception as e:
            logger.warning(
                "Resolution error for flag %s: %s. Using default.",
                key, e,
            )
            return default

    async def batch_resolve(
        self,
        keys: List[str],
        context: Optional[FeatureContext] = None,
    ) -> Dict[str, FeatureEvaluationResult]:
        """
        Resolve multiple feature flags in batch.

        Args:
            keys: List of feature flag keys.
            context: Shared evaluation context.

        Returns:
            Dictionary mapping keys to results.
        """
        results: Dict[str, FeatureEvaluationResult] = {}
        for key in keys:
            try:
                results[key] = await self.resolve(key, context)
            except FeatureFlagNotFoundError:
                results[key] = FeatureEvaluationResult(
                    key=key,
                    value=False,
                    enabled=False,
                    result=EvaluationResult.MISS,
                    reason="flag_not_found",
                )
            except Exception as e:
                results[key] = FeatureEvaluationResult(
                    key=key,
                    value=False,
                    enabled=False,
                    result=EvaluationResult.ERROR,
                    reason=str(e),
                )
        return results

    def _get_flag(
        self,
        key: str,
    ) -> Optional[FeatureFlag]:
        """Get a flag definition from registry."""
        if self._registry:
            return self._registry.get(key)
        if self._manager and self._manager.get_registry():
            return self._manager.get_registry().get(key)
        return None

    def _build_cache_key(
        self,
        key: str,
        context: Optional[FeatureContext],
    ) -> str:
        """Build a cache key from flag key and context."""
        if context and context.target_id:
            return f"{key}:{context.target_id}"
        return key

    def get_stats(self) -> Dict[str, Any]:
        """Get resolver statistics."""
        total = self._resolution_count
        return {
            "resolutions": self._resolution_count,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_ratio": (
                self._cache_hits / total if total > 0 else 0.0
            ),
            "errors": self._error_count,
        }

    def reset_stats(self) -> None:
        """Reset all resolver statistics."""
        self._resolution_count = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._error_count = 0


class CachedResolver(FeatureResolver):
    """
    Resolver with enhanced caching capabilities.

    Extends the base FeatureResolver with support
    for preloading, bulk caching, and smart cache
    invalidation based on flag version changes.

    Usage:
        resolver = CachedResolver(manager)
        await resolver.preload(["flag1", "flag2"])
        result = await resolver.resolve("flag1", context)
    """

    def __init__(
        self,
        manager: Any = None,
        registry: Any = None,
        evaluator: Any = None,
        cache: Any = None,
    ) -> None:
        super().__init__(manager, registry, evaluator, cache)
        self._preloaded_keys: set[str] = set()
        self._preload_version: int = 0

    async def preload(
        self,
        keys: List[str],
        context: Optional[FeatureContext] = None,
    ) -> int:
        """
        Preload flag values into cache.

        Args:
            keys: List of flag keys to preload.
            context: Shared evaluation context.

        Returns:
            Number of flags preloaded.
        """
        count = 0
        for key in keys:
            try:
                result = await super().resolve(key, context, use_cache=False)
                self._preloaded_keys.add(key)
                count += 1
            except Exception as e:
                logger.warning(
                    "Preload failed for %s: %s", key, e,
                )
        return count

    async def invalidate_preloaded(
        self,
        keys: Optional[List[str]] = None,
    ) -> int:
        """
        Invalidate preloaded cache entries.

        Args:
            keys: Specific keys to invalidate, or None for all.

        Returns:
            Number of entries invalidated.
        """
        if keys is None:
            keys_to_invalidate = list(self._preloaded_keys)
            self._preloaded_keys.clear()
        else:
            keys_to_invalidate = [k for k in keys if k in self._preloaded_keys]
            for k in keys_to_invalidate:
                self._preloaded_keys.discard(k)

        if self._cache and keys_to_invalidate:
            return await self._cache.invalidate(keys_to_invalidate)
        return 0

    def is_preloaded(self, key: str) -> bool:
        """Check if a flag key is preloaded."""
        return key in self._preloaded_keys