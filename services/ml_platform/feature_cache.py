"""
ICYQuant Feature Cache - Feature value caching layer.

Provides in-memory caching for frequently accessed feature values
to reduce latency for real-time inference and repeated computations.
Supports TTL-based expiration and LRU eviction.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A single cache entry."""

    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    ttl_seconds: int = 300  # default 5 minutes
    hit_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    size_bytes: int = 0

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at


@dataclass
class CacheStats:
    """Cache statistics."""

    total_entries: int = 0
    hit_count: int = 0
    miss_count: int = 0
    eviction_count: int = 0
    expiration_count: int = 0

    @property
    def hit_ratio(self) -> float:
        total = self.hit_count + self.miss_count
        if total == 0:
            return 0.0
        return self.hit_count / total


class FeatureCache:
    """Feature value cache with TTL and LRU eviction.

    Multiple cache levels:
    - L1: In-memory (fastest, small capacity)
    - L2: TBD (e.g., Redis, for distributed access)
    """

    def __init__(
        self,
        max_entries: int = 10000,
        default_ttl_seconds: int = 300,
        max_memory_mb: int = 512,
    ) -> None:
        self._max_entries = max_entries
        self._default_ttl = default_ttl_seconds
        self._max_memory = max_memory_mb * 1024 * 1024

        # LRU cache (OrderedDict tracks access order)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()

        self._stats = CacheStats()
        self._current_memory: int = 0

    # -- Read --

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache. Returns None on miss or expired."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats.miss_count += 1
                return None

            if entry.is_expired:
                self._cache.pop(key, None)
                self._stats.expiration_count += 1
                self._stats.miss_count += 1
                return None

            # LRU: move to end (most recently used)
            self._cache.move_to_end(key)
            entry.hit_count += 1
            entry.last_accessed = time.time()
            self._stats.hit_count += 1
            logger.debug("Cache HIT: %s (hits=%d)", key, entry.hit_count)
            return entry.value

    async def get_batch(self, keys: List[str]) -> Dict[str, Optional[Any]]:
        """Get multiple values from cache."""
        result: Dict[str, Optional[Any]] = {}
        for key in keys:
            result[key] = await self.get(key)
        return result

    # -- Write --

    async def put(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Put a value into the cache."""
        import sys
        ttl = ttl_seconds or self._default_ttl

        async with self._lock:
            entry = CacheEntry(
                key=key,
                value=value,
                ttl_seconds=ttl,
                size_bytes=sys.getsizeof(value),
            )

            # Evict if needed
            await self._ensure_capacity(entry.size_bytes)

            self._cache[key] = entry
            self._cache.move_to_end(key)
            self._current_memory += entry.size_bytes
            self._stats.total_entries = len(self._cache)

    async def put_batch(self, items: Dict[str, Any], ttl_seconds: Optional[int] = None) -> None:
        """Put multiple values into cache."""
        for key, value in items.items():
            await self.put(key, value, ttl_seconds)

    # -- Eviction --

    async def _ensure_capacity(self, new_entry_size: int) -> None:
        """Ensure cache has capacity for a new entry."""
        # Check entry count limit
        while len(self._cache) >= self._max_entries:
            await self._evict_one()

        # Check memory limit
        while self._current_memory + new_entry_size > self._max_memory:
            await self._evict_one()

    async def _evict_one(self) -> None:
        """Evict the least recently used entry."""
        if not self._cache:
            return
        key, entry = self._cache.popitem(last=False)  # LRU: remove first
        self._current_memory -= entry.size_bytes
        self._stats.eviction_count += 1
        logger.debug("Cache evicted: %s (age=%.1fs, hits=%d)", key, entry.age_seconds, entry.hit_count)

    # -- Maintenance --

    async def invalidate(self, key: str) -> bool:
        """Explicitly invalidate a cache entry."""
        async with self._lock:
            entry = self._cache.pop(key, None)
            if entry:
                self._current_memory -= entry.size_bytes
                return True
            return False

    async def invalidate_by_prefix(self, prefix: str) -> int:
        """Invalidate all entries with keys starting with prefix."""
        async with self._lock:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for key in keys_to_remove:
                self._current_memory -= self._cache[key].size_bytes
                del self._cache[key]
            return len(keys_to_remove)

    async def clear(self) -> None:
        """Clear the entire cache."""
        async with self._lock:
            self._cache.clear()
            self._current_memory = 0
            self._stats = CacheStats()

    async def clean_expired(self) -> int:
        """Remove all expired entries."""
        async with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired]
            for key in expired_keys:
                self._current_memory -= self._cache[key].size_bytes
                del self._cache[key]
                self._stats.expiration_count += 1
            return len(expired_keys)

    # -- Stats --

    def get_stats(self) -> CacheStats:
        """Get current cache statistics."""
        self._stats.total_entries = len(self._cache)
        return self._stats

    @property
    def size(self) -> int:
        return len(self._cache)
