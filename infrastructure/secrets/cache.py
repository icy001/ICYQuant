"""
Secrets cache.

Provides TTL-based caching for secret
values with thread-safe operations,
cache invalidation, and expiration
management.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .exceptions import SecretCacheError


class SecretsCache:
    """
    Thread-safe secrets cache.

    Provides TTL-based caching with LRU eviction,
    supporting cache invalidation, expiration
    checks, and periodic cleanup of expired
    entries.

    Usage:
        cache = SecretsCache(ttl=300, max_size=1000)
        cache.put("db/password", "secret123")
        value = cache.get("db/password")
    """

    def __init__(
        self,
        ttl: int = 300,
        max_size: int = 1000,
    ) -> None:
        """
        Initialize secrets cache.

        Args:
            ttl: Default time-to-live in seconds.
            max_size: Maximum number of cached entries.
        """
        self._default_ttl = ttl
        self._max_size = max_size
        self._lock = threading.RLock()
        # key -> (value, expires_at, created_at, access_count)
        self._cache: OrderedDict[str, Tuple[Any, float, float, int]] = OrderedDict()
        # Key to namespace mapping
        self._key_namespace: Dict[str, str] = {}
        # Statistics
        self._hits = 0
        self._misses = 0
        self._expired = 0

    # ── Core Operations ──

    def get(
        self,
        key: str,
        namespace: str = "default",
    ) -> Optional[Any]:
        """
        Get a cached secret value.

        Args:
            key: The secret key.
            namespace: Namespace.

        Returns:
            Cached value or None if not found/expired.
        """
        cache_key = f"{namespace}/{key}"

        with self._lock:
            if cache_key not in self._cache:
                self._misses += 1
                return None

            value, expires_at, created_at, access_count = self._cache[cache_key]

            # Check expiration
            now = time.time()
            if now > expires_at:
                # Entry expired
                del self._cache[cache_key]
                self._key_namespace.pop(cache_key, None)
                self._expired += 1
                self._misses += 1
                return None

            # Move to end for LRU
            self._cache.move_to_end(cache_key)

            # Update access count
            self._cache[cache_key] = (value, expires_at, created_at, access_count + 1)

            self._hits += 1
            return value

    def put(
        self,
        key: str,
        value: Any,
        namespace: str = "default",
        ttl: Optional[int] = None,
    ) -> None:
        """
        Cache a secret value.

        Args:
            key: The secret key.
            value: The value to cache.
            namespace: Namespace.
            ttl: Optional custom TTL (seconds).
        """
        cache_key = f"{namespace}/{key}"
        effective_ttl = ttl if ttl is not None else self._default_ttl
        expires_at = time.time() + effective_ttl

        with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self._max_size and cache_key not in self._cache:
                self._evict_lru()

            self._cache[cache_key] = (value, expires_at, time.time(), 0)
            self._key_namespace[cache_key] = namespace
            # Move to end (most recently used)
            self._cache.move_to_end(cache_key)

    def invalidate(
        self,
        key: str,
        namespace: str = "default",
    ) -> bool:
        """
        Invalidate a cached entry.

        Args:
            key: The secret key.
            namespace: Namespace.

        Returns:
            True if key was found and removed.
        """
        cache_key = f"{namespace}/{key}"

        with self._lock:
            if cache_key in self._cache:
                del self._cache[cache_key]
                self._key_namespace.pop(cache_key, None)
                return True
            return False

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._key_namespace.clear()

    def clear_namespace(self, namespace: str) -> int:
        """
        Clear all entries in a namespace.

        Args:
            namespace: Namespace to clear.

        Returns:
            Number of entries cleared.
        """
        with self._lock:
            to_remove = [
                key for key in self._cache
                if key.startswith(f"{namespace}/")
            ]
            for key in to_remove:
                del self._cache[key]
                self._key_namespace.pop(key, None)
            return len(to_remove)

    # ── Expiration Management ──

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed.
        """
        with self._lock:
            now = time.time()
            expired_keys = [
                key for key, (_, expires_at, _, _) in self._cache.items()
                if now > expires_at
            ]
            for key in expired_keys:
                del self._cache[key]
                self._key_namespace.pop(key, None)

            self._expired += len(expired_keys)
            return len(expired_keys)

    def get_remaining_ttl(
        self,
        key: str,
        namespace: str = "default",
    ) -> float:
        """
        Get remaining TTL for a cached entry.

        Args:
            key: The secret key.
            namespace: Namespace.

        Returns:
            Remaining TTL in seconds, or 0 if not cached.
        """
        cache_key = f"{namespace}/{key}"

        with self._lock:
            if cache_key not in self._cache:
                return 0.0

            _, expires_at, _, _ = self._cache[cache_key]
            remaining = expires_at - time.time()
            return max(0.0, remaining)

    def is_cached(
        self,
        key: str,
        namespace: str = "default",
    ) -> bool:
        """Check if a key is cached and not expired."""
        return self.get(key, namespace) is not None

    # ── LRU Eviction ──

    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if not self._cache:
            return

        # First item is the least recently used
        lru_key = next(iter(self._cache))
        del self._cache[lru_key]
        self._key_namespace.pop(lru_key, None)

    # ── Statistics ──

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

            return {
                "entries": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "expired": self._expired,
                "hit_rate": round(hit_rate, 4),
                "ttl": self._default_ttl,
            }

    def size(self) -> int:
        """Get number of cached entries."""
        with self._lock:
            return len(self._cache)

    def keys(self, namespace: Optional[str] = None) -> List[str]:
        """
        List cached keys.

        Args:
            namespace: Optional namespace filter.

        Returns:
            List of cached keys.
        """
        with self._lock:
            if namespace:
                prefix = f"{namespace}/"
                return [k[len(prefix):] for k in self._cache if k.startswith(prefix)]
            return [k.split("/", 1)[1] if "/" in k else k for k in self._cache]

    # ── Async Support ──

    async def async_get(
        self,
        key: str,
        namespace: str = "default",
    ) -> Optional[Any]:
        """Async version of get."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get, key, namespace)

    async def async_put(
        self,
        key: str,
        value: Any,
        namespace: str = "default",
        ttl: Optional[int] = None,
    ) -> None:
        """Async version of put."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.put, key, value, namespace, ttl)

    async def async_invalidate(
        self,
        key: str,
        namespace: str = "default",
    ) -> bool:
        """Async version of invalidate."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.invalidate, key, namespace)
