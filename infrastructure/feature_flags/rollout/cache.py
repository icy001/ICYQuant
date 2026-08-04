"""
Rollout-specific cache layer.

Provides hash cache and assignment cache
with TTL-based eviction for optimal
rollout evaluation performance.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional


class RolloutCache:
    """
    Dual-layer cache for rollout evaluations.

    Separately caches:
        - Hash results (key → hash value)
        - Assignment results (flag+target → assignment)

    Both caches support TTL and LRU eviction.

    Usage:
        cache = RolloutCache()
        await cache.set_hash("flag:account_123", 4567)
        value = await cache.get_hash("flag:account_123")
        # value == 4567 or None
    """

    def __init__(
        self,
        hash_ttl: float = 300.0,
        assignment_ttl: float = 600.0,
        max_hash_entries: int = 50000,
        max_assignment_entries: int = 100000,
    ) -> None:
        """
        Initialize the rollout cache.

        Args:
            hash_ttl: TTL for hash entries in seconds.
            assignment_ttl: TTL for assignment entries.
            max_hash_entries: Max hash cache size.
            max_assignment_entries: Max assignment cache size.
        """
        self._hash_cache: Dict[str, tuple] = {}  # (value, expire_time)
        self._assignment_cache: Dict[str, tuple] = {}  # (value, expire_time)
        self._hash_ttl = hash_ttl
        self._assignment_ttl = assignment_ttl
        self._max_hash = max_hash_entries
        self._max_assignment = max_assignment_entries
        self._lock = asyncio.Lock()
        self._hash_hits = 0
        self._hash_misses = 0
        self._assignment_hits = 0
        self._assignment_misses = 0
        self._hash_sets = 0
        self._assignment_sets = 0

    async def get_hash(self, key: str) -> Optional[int]:
        """
        Get a cached hash value.

        Args:
            key: Cache key.

        Returns:
            Cached hash or None.
        """
        async with self._lock:
            entry = self._hash_cache.get(key)
            if entry is None:
                self._hash_misses += 1
                return None

            value, expire_time = entry
            if expire_time < time.time():
                del self._hash_cache[key]
                self._hash_misses += 1
                return None

            self._hash_hits += 1
            return value

    async def set_hash(
        self,
        key: str,
        value: int,
        ttl: Optional[float] = None,
    ) -> None:
        """
        Cache a hash value.

        Args:
            key: Cache key.
            value: Hash value.
            ttl: Optional TTL override.
        """
        ttl = ttl or self._hash_ttl
        async with self._lock:
            self._hash_cache[key] = (value, time.time() + ttl)
            self._hash_sets += 1
            self._evict_hash()

    async def get_assignment(self, key: str) -> Optional[Any]:
        """
        Get a cached assignment.

        Args:
            key: Cache key.

        Returns:
            Cached assignment or None.
        """
        async with self._lock:
            entry = self._assignment_cache.get(key)
            if entry is None:
                self._assignment_misses += 1
                return None

            value, expire_time = entry
            if expire_time < time.time():
                del self._assignment_cache[key]
                self._assignment_misses += 1
                return None

            self._assignment_hits += 1
            return value

    async def set_assignment(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
    ) -> None:
        """
        Cache an assignment result.

        Args:
            key: Cache key.
            value: Assignment result.
            ttl: Optional TTL override.
        """
        ttl = ttl or self._assignment_ttl
        async with self._lock:
            self._assignment_cache[key] = (value, time.time() + ttl)
            self._assignment_sets += 1
            self._evict_assignment()

    def invalidate_hash(self, key: Optional[str] = None) -> int:
        """
        Invalidate hash cache entries.

        Args:
            key: Specific key (None = all).

        Returns:
            Number of invalidated entries.
        """
        if key is None:
            count = len(self._hash_cache)
            self._hash_cache.clear()
            return count

        if key in self._hash_cache:
            del self._hash_cache[key]
            return 1
        return 0

    def invalidate_assignment(self, key: Optional[str] = None) -> int:
        """
        Invalidate assignment cache entries."""
        if key is None:
            count = len(self._assignment_cache)
            self._assignment_cache.clear()
            return count

        if key in self._assignment_cache:
            del self._assignment_cache[key]
            return 1
        return 0

    def _evict_hash(self) -> None:
        """Evict expired/old hash entries."""
        now = time.time()
        expired = [k for k, (_, exp) in self._hash_cache.items() if exp < now]
        for k in expired:
            del self._hash_cache[k]

        if len(self._hash_cache) > self._max_hash:
            excess = len(self._hash_cache) - self._max_hash
            keys = list(self._hash_cache.keys())
            for k in keys[:excess]:
                del self._hash_cache[k]

    def _evict_assignment(self) -> None:
        """Evict expired/old assignment entries."""
        now = time.time()
        expired = [k for k, (_, exp) in self._assignment_cache.items() if exp < now]
        for k in expired:
            del self._assignment_cache[k]

        if len(self._assignment_cache) > self._max_assignment:
            excess = len(self._assignment_cache) - self._max_assignment
            keys = list(self._assignment_cache.keys())
            for k in keys[:excess]:
                del self._assignment_cache[k]

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_hash = self._hash_hits + self._hash_misses
        total_assign = self._assignment_hits + self._assignment_misses
        return {
            "hash_cache_size": len(self._hash_cache),
            "assignment_cache_size": len(self._assignment_cache),
            "hash_hits": self._hash_hits,
            "hash_misses": self._hash_misses,
            "hash_hit_rate": (
                self._hash_hits / total_hash if total_hash > 0 else 0.0
            ),
            "assignment_hits": self._assignment_hits,
            "assignment_misses": self._assignment_misses,
            "assignment_hit_rate": (
                self._assignment_hits / total_assign
                if total_assign > 0
                else 0.0
            ),
            "hash_sets": self._hash_sets,
            "assignment_sets": self._assignment_sets,
        }

    def clear(self) -> None:
        """Clear all caches."""
        self._hash_cache.clear()
        self._assignment_cache.clear()
        self._hash_hits = 0
        self._hash_misses = 0
        self._assignment_hits = 0
        self._assignment_misses = 0
        self._hash_sets = 0
        self._assignment_sets = 0
