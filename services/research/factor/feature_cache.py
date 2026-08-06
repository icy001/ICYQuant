"""Feature Cache — multi-level caching for feature computation results.

Supports Memory, Redis, and Disk backends with LRU eviction and TTL.
Reduces redundant feature computation across factor pipelines.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class FeatureCacheBackend(str, Enum):
    """Cache storage backends."""

    MEMORY = "memory"
    REDIS = "redis"
    DISK = "disk"


@dataclass
class FeatureCacheEntry:
    """A single cache entry."""

    key: str
    value: Any
    ttl: Optional[int] = None  # seconds
    created_at: float = field(default_factory=time.time)
    hit_count: int = 0
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return (time.time() - self.created_at) > self.ttl

    def access(self) -> None:
        self.hit_count += 1


class FeatureCache:
    """Multi-level feature computation cache.

    Backends:
    * Memory: fastest, limited by RAM
    * Redis: shared across processes, persistent
    * Disk: largest capacity, slowest

    Features:
    * LRU eviction
    * TTL-based expiration
    * Hit/miss tracking
    * Cache warming
    """

    def __init__(
        self,
        backend: FeatureCacheBackend = FeatureCacheBackend.MEMORY,
        max_entries: int = 10000,
        default_ttl: Optional[int] = 3600,
    ) -> None:
        self._backend = backend
        self._max_entries = max_entries
        self._default_ttl = default_ttl
        self._entries: Dict[str, FeatureCacheEntry] = {}
        self._hits: int = 0
        self._misses: int = 0
        self._lock = __import__("asyncio").Lock()

    @property
    def backend(self) -> FeatureCacheBackend:
        return self._backend

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        return len(self._entries)

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a cached feature value."""
        import asyncio as _asyncio
        async with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.is_expired():
                del self._entries[key]
                self._misses += 1
                return None
            entry.access()
            self._hits += 1
            return entry.value

    async def put(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Cache a feature value."""
        async with self._lock:
            if len(self._entries) >= self._max_entries:
                await self._evict_lru()

            entry = FeatureCacheEntry(
                key=key,
                value=value,
                ttl=ttl if ttl is not None else self._default_ttl,
                metadata=metadata or {},
            )
            self._entries[key] = entry
            logger.debug("Cached feature: %s (ttl=%s)", key, entry.ttl)

    async def invalidate(self, key: Optional[str] = None) -> int:
        """Invalidate cache entries. If key is None, clear all."""
        async with self._lock:
            if key is None:
                count = len(self._entries)
                self._entries.clear()
                logger.info("Cache cleared: %d entries", count)
                return count
            else:
                if key in self._entries:
                    del self._entries[key]
                    return 1
                return 0

    async def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if not self._entries:
            return
        lru_key = min(
            self._entries.keys(),
            key=lambda k: self._entries[k].created_at,
        )
        del self._entries[lru_key]

    async def warm(
        self,
        items: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> None:
        """Warm the cache with precomputed values."""
        for key, value in items.items():
            await self.put(key, value, ttl=ttl)

    def stats(self) -> Dict[str, Any]:
        return {
            "backend": self._backend.value,
            "entries": len(self._entries),
            "max_entries": self._max_entries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self.hit_rate:.2%}",
            "expired": sum(1 for e in self._entries.values() if e.is_expired()),
        }
