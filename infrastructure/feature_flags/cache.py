"""
Feature flag platform cache.

Provides local caching for feature flag
evaluations with TTL, version-based invalidation,
and refresh support.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .constants import DEFAULT_CACHE_MAX_SIZE, DEFAULT_CACHE_TTL
from .exceptions import FeatureFlagCacheError
from .models import FeatureFlagCacheEntry

logger = logging.getLogger(__name__)


class FeatureFlagCache:
    """
    Local cache for feature flag evaluations.

    Caches evaluated flag values with TTL-based
    expiration and version-based invalidation.
    Supports manual refresh and bulk invalidation
    when flag definitions change.

    Usage:
        cache = FeatureFlagCache(ttl=60)
        await cache.put("my.feature", True)
        value = await cache.get("my.feature")  # True
    """

    def __init__(
        self,
        ttl: int = DEFAULT_CACHE_TTL,
        max_size: int = DEFAULT_CACHE_MAX_SIZE,
    ) -> None:
        """
        Initialize the feature flag cache.

        Args:
            ttl: Time-to-live in seconds.
            max_size: Maximum number of cached entries.
        """
        self._ttl = ttl
        self._max_size = max_size
        self._entries: Dict[str, FeatureFlagCacheEntry] = {}
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
        self._invalidations = 0
        self._enabled = True

    async def get(
        self,
        key: str,
    ) -> Optional[Any]:
        """
        Get a cached value by key.

        Returns None if the key is not cached or
        the entry has expired.

        Args:
            key: Cache key (typically flag key).

        Returns:
            Cached value or None.
        """
        if not self._enabled:
            self._misses += 1
            return None

        async with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.expires_at and datetime.utcnow() > entry.expires_at:
                del self._entries[key]
                self._misses += 1
                return None

            self._hits += 1
            return entry.value

    async def put(
        self,
        key: str,
        value: Any,
        version: int = 0,
        ttl: Optional[int] = None,
    ) -> None:
        """
        Store a value in the cache.

        Automatically evicts the oldest entry if
        the cache exceeds max_size.

        Args:
            key: Cache key.
            value: Value to cache.
            version: Version counter for invalidation.
            ttl: Optional per-entry TTL override in seconds.
        """
        if not self._enabled:
            return

        effective_ttl = ttl if ttl is not None else self._ttl
        expires_at = datetime.utcnow() + timedelta(seconds=effective_ttl)

        async with self._lock:
            # Evict if at capacity
            if len(self._entries) >= self._max_size and key not in self._entries:
                self._evict_oldest()

            self._entries[key] = FeatureFlagCacheEntry(
                key=key,
                value=value,
                version=version,
                expires_at=expires_at,
                cached_at=datetime.utcnow(),
            )

    async def delete(
        self,
        key: str,
    ) -> bool:
        """
        Delete a single cache entry.

        Args:
            key: Cache key to delete.

        Returns:
            True if the key was deleted.
        """
        async with self._lock:
            if key in self._entries:
                del self._entries[key]
                self._invalidations += 1
                return True
            return False

    async def invalidate(
        self,
        keys: Optional[List[str]] = None,
    ) -> int:
        """
        Invalidate cache entries.

        If keys is provided, only those keys are
        invalidated. Otherwise, all entries are
        cleared.

        Args:
            keys: Specific keys to invalidate.

        Returns:
            Number of entries invalidated.
        """
        async with self._lock:
            if keys is None:
                count = len(self._entries)
                self._entries.clear()
                self._invalidations += count
                return count
            else:
                count = 0
                for key in keys:
                    if key in self._entries:
                        del self._entries[key]
                        count += 1
                self._invalidations += count
                return count

    async def refresh(
        self,
        key: str,
        value_provider: Any,
        version: int = 0,
    ) -> Any:
        """
        Refresh a cache entry by calling the provider.

        Args:
            key: Cache key.
            value_provider: Async callable that returns the value.
            version: Version counter.

        Returns:
            Fresh value.
        """
        try:
            value = await value_provider()
        except Exception as e:
            raise FeatureFlagCacheError(
                operation="refresh",
                key=key,
                reason=str(e),
            )

        await self.put(key, value, version=version)
        return value

    async def get_or_refresh(
        self,
        key: str,
        value_provider: Any,
        version: int = 0,
    ) -> Any:
        """
        Get cached value or refresh if missing/expired.

        Args:
            key: Cache key.
            value_provider: Async callable for value.
            version: Version counter.

        Returns:
            Cached or freshly computed value.
        """
        cached = await self.get(key)
        if cached is not None:
            return cached
        return await self.refresh(key, value_provider, version=version)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Statistics dictionary.
        """
        total = self._hits + self._misses
        hit_ratio = (self._hits / total) if total > 0 else 0.0
        return {
            "enabled": self._enabled,
            "entries": len(self._entries),
            "max_size": self._max_size,
            "ttl_seconds": self._ttl,
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio": hit_ratio,
            "invalidations": self._invalidations,
        }

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the cache."""
        self._enabled = enabled

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._entries.clear()
            self._invalidations += self._invalidations

    def _evict_oldest(self) -> None:
        """Evict the oldest entry from the cache."""
        if not self._entries:
            return

        now = datetime.utcnow()
        oldest_key = None
        oldest_time = None

        for key, entry in self._entries.items():
            if oldest_time is None or entry.cached_at < oldest_time:
                oldest_key = key
                oldest_time = entry.cached_at

        if oldest_key:
            del self._entries[oldest_key]
            logger.debug(
                "Evicted oldest cache entry: %s", oldest_key,
            )

    async def cleanup_expired(self) -> int:
        """
        Remove all expired entries from the cache.

        Returns:
            Number of entries removed.
        """
        async with self._lock:
            now = datetime.utcnow()
            expired_keys = [
                key
                for key, entry in self._entries.items()
                if entry.expires_at and now > entry.expires_at
            ]

            for key in expired_keys:
                del self._entries[key]

            if expired_keys:
                logger.debug(
                    "Cleaned up %d expired cache entries",
                    len(expired_keys),
                )

            return len(expired_keys)