"""
Storage cache layer.

Provides Redis-based metadata caching for
storage objects, reducing object storage
access for frequently accessed data.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .metadata import ExtendedMetadata


class StorageCache:
    """
    Storage metadata cache.

    Caches object metadata in Redis to avoid
    repeated object storage calls. Supports
    TTL-based expiration and invalidation.

    Features:
    - Metadata caching with configurable TTL
    - Hit/Miss tracking
    - Bulk invalidation support

    Usage:
        cache = StorageCache(redis_client)
        await cache.set_metadata("key", metadata)
        cached = await cache.get_metadata("key")
    """

    KEY_PREFIX = "icyquant:storage:meta"

    def __init__(
        self,
        redis_client: Any = None,
        ttl: int = 3600,
    ) -> None:
        """
        Initialize storage cache.

        Args:
            redis_client: Redis async client.
            ttl: Default cache TTL in seconds.
        """

        self._redis = redis_client
        self._default_ttl = ttl
        self._enabled = redis_client is not None

    @property
    def is_enabled(
        self,
    ) -> bool:
        """Check if cache is enabled."""
        return self._enabled

    @property
    def default_ttl(
        self,
    ) -> int:
        """Get default TTL."""
        return self._default_ttl

    def _cache_key(
        self,
        key: str,
    ) -> str:
        """
        Build cache key.

        Args:
            key: Object key.

        Returns:
            Cache key string.
        """

        return f"{self.KEY_PREFIX}:{key}"

    async def get_metadata(
        self,
        key: str,
    ) -> Optional[ExtendedMetadata]:
        """
        Get cached metadata for an object.

        Args:
            key: Object key.

        Returns:
            ExtendedMetadata if cached, None otherwise.
        """

        if not self._enabled:
            return None

        try:
            cached = await self._redis.get(
                self._cache_key(key)
            )
            if cached is None:
                return None

            data = json.loads(cached)
            return ExtendedMetadata.from_dict(data)
        except Exception:
            return None

    async def set_metadata(
        self,
        key: str,
        metadata: ExtendedMetadata,
        ttl: Optional[int] = None,
    ) -> None:
        """
        Cache object metadata.

        Args:
            key: Object key.
            metadata: Metadata to cache.
            ttl: Cache TTL in seconds.
        """

        if not self._enabled:
            return

        try:
            ttl = ttl or self._default_ttl
            data = json.dumps(metadata.to_dict())
            await self._redis.set(
                self._cache_key(key),
                data,
                ex=ttl,
            )
        except Exception:
            pass

    async def invalidate(
        self,
        key: str,
    ) -> None:
        """
        Invalidate cached metadata.

        Args:
            key: Object key.
        """

        if not self._enabled:
            return

        try:
            await self._redis.delete(
                self._cache_key(key)
            )
        except Exception:
            pass

    async def invalidate_prefix(
        self,
        prefix: str,
    ) -> int:
        """
        Invalidate all cached keys matching a prefix.

        Args:
            prefix: Key prefix to match.

        Returns:
            Number of invalidated keys.
        """

        if not self._enabled:
            return 0

        count = 0
        pattern = f"{self.KEY_PREFIX}:{prefix}*"

        try:
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor,
                    match=pattern,
                    count=100,
                )
                if keys:
                    await self._redis.delete(*keys)
                    count += len(keys)
                if cursor == 0:
                    break
        except Exception:
            pass

        return count

    async def get_cache_stats(
        self,
    ) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats.
        """

        return {
            "enabled": self._enabled,
            "default_ttl": self._default_ttl,
            "key_prefix": self.KEY_PREFIX,
        }