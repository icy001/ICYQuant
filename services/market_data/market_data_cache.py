"""
Market Data Cache — enterprise caching layer for high-frequency
market data access (tick, quote, orderbook, kline caches).

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CachePolicy(str, Enum):
    LRU = "lru"               # Least Recently Used
    TTL = "ttl"               # Time-To-Live
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"


@dataclass
class CacheEntry:
    """A single cache entry."""

    key: str = ""
    value: Any = None
    created_at_ns: int = 0
    last_accessed_ns: int = 0
    access_count: int = 0
    ttl_ns: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self, now_ns: int) -> bool:
        if self.ttl_ns <= 0:
            return False
        return (now_ns - self.created_at_ns) > self.ttl_ns


@dataclass
class CacheStats:
    """Cache performance statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    size: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0


class MarketDataCache:
    """
    Enterprise market data cache with namespace isolation.

    Namespaces:
    - tick: Latest tick data per instrument
    - quote: Latest quote (bid/ask) data
    - orderbook: Full orderbook snapshots
    - kline: Cached kline bars
    - instrument: Instrument metadata

    Supports TTL-based expiration and LRU eviction.
    """

    DEFAULT_TTL_NS: dict[str, int] = {
        "tick": 5_000_000_000,         # 5s
        "quote": 1_000_000_000,        # 1s
        "orderbook": 500_000_000,      # 500ms
        "kline": 60_000_000_000,       # 60s
        "instrument": 300_000_000_000, # 300s (5 min)
    }

    def __init__(self, max_entries: int = 100_000) -> None:
        self._max_entries = max_entries
        self._namespaces: dict[str, dict[str, CacheEntry]] = {}
        self._stats: dict[str, CacheStats] = {}

    async def initialize(self) -> None:
        logger.info("MarketDataCache initialized (max_entries: %d)", self._max_entries)

    # ── Get/Put ────────────────────────────────────

    async def get(self, namespace: str, key: str) -> Optional[Any]:
        """Retrieve a cached value."""
        self._ensure_namespace(namespace)
        now_ns = self._now_ns()
        stats = self._get_stats(namespace)

        entry = self._namespaces[namespace].get(key)
        if entry is None:
            stats.misses += 1
            return None

        if entry.is_expired(now_ns):
            del self._namespaces[namespace][key]
            stats.expirations += 1
            stats.misses += 1
            stats.size = len(self._namespaces[namespace])
            return None

        entry.last_accessed_ns = now_ns
        entry.access_count += 1
        stats.hits += 1
        return entry.value

    async def put(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl_ns: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Store a value in the cache."""
        self._ensure_namespace(namespace)
        ns_store = self._namespaces[namespace]

        ttl = ttl_ns if ttl_ns is not None else self.DEFAULT_TTL_NS.get(namespace, 60_000_000_000)
        now_ns = self._now_ns()

        entry = CacheEntry(
            key=key,
            value=value,
            created_at_ns=now_ns,
            last_accessed_ns=now_ns,
            access_count=1,
            ttl_ns=ttl,
            metadata=metadata or {},
        )

        # Evict if needed
        if key not in ns_store and len(ns_store) >= self._max_entries:
            await self._evict(namespace)

        ns_store[key] = entry
        self._get_stats(namespace).size = len(ns_store)

    async def get_or_put(
        self,
        namespace: str,
        key: str,
        factory: Any,  # async callable
        ttl_ns: Optional[int] = None,
    ) -> Optional[Any]:
        """Get from cache or compute and store."""
        value = await self.get(namespace, key)
        if value is not None:
            return value

        import asyncio
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        if value is not None:
            await self.put(namespace, key, value, ttl_ns)
        return value

    # ── Bulk operations ────────────────────────────

    async def get_multi(self, namespace: str, keys: list[str]) -> dict[str, Optional[Any]]:
        """Retrieve multiple keys atomically."""
        result: dict[str, Optional[Any]] = {}
        for key in keys:
            result[key] = await self.get(namespace, key)
        return result

    async def put_multi(
        self,
        namespace: str,
        items: dict[str, Any],
        ttl_ns: Optional[int] = None,
    ) -> None:
        """Store multiple items."""
        for key, value in items.items():
            await self.put(namespace, key, value, ttl_ns)

    async def invalidate(self, namespace: str, key: str) -> bool:
        """Remove a specific entry."""
        self._ensure_namespace(namespace)
        if key in self._namespaces[namespace]:
            del self._namespaces[namespace][key]
            self._get_stats(namespace).size = len(self._namespaces[namespace])
            return True
        return False

    async def invalidate_namespace(self, namespace: str) -> int:
        """Clear an entire namespace."""
        self._ensure_namespace(namespace)
        count = len(self._namespaces[namespace])
        self._namespaces[namespace].clear()
        self._get_stats(namespace).size = 0
        return count

    async def clear(self) -> None:
        """Clear all caches."""
        self._namespaces.clear()
        self._stats.clear()

    # ── Maintenance ────────────────────────────────

    async def cleanup_expired(self) -> int:
        """Remove all expired entries across all namespaces."""
        now_ns = self._now_ns()
        total_removed = 0

        for namespace, store in self._namespaces.items():
            expired_keys = [k for k, v in store.items() if v.is_expired(now_ns)]
            for k in expired_keys:
                del store[k]
                total_removed += 1
            if expired_keys:
                self._get_stats(namespace).expirations += len(expired_keys)
                self._get_stats(namespace).size = len(store)

        return total_removed

    # ── Stats ──────────────────────────────────────

    async def get_stats(self, namespace: str) -> CacheStats:
        """Get statistics for a namespace."""
        self._ensure_namespace(namespace)
        stats = self._get_stats(namespace)
        stats.size = len(self._namespaces[namespace])
        stats.max_size = self._max_entries
        return stats

    async def get_all_stats(self) -> dict[str, CacheStats]:
        """Get statistics for all namespaces."""
        result: dict[str, CacheStats] = {}
        for ns in self._namespaces:
            result[ns] = await self.get_stats(ns)
        return result

    @property
    def total_entries(self) -> int:
        return sum(len(s) for s in self._namespaces.values())

    # ── Internal ───────────────────────────────────

    def _ensure_namespace(self, namespace: str) -> None:
        if namespace not in self._namespaces:
            self._namespaces[namespace] = {}

    def _get_stats(self, namespace: str) -> CacheStats:
        if namespace not in self._stats:
            self._stats[namespace] = CacheStats()
        return self._stats[namespace]

    async def _evict(self, namespace: str) -> None:
        """Evict the least recently used entry."""
        store = self._namespaces[namespace]
        if not store:
            return

        # Find LRU entry
        oldest_key = min(store, key=lambda k: store[k].last_accessed_ns)
        del store[oldest_key]
        self._get_stats(namespace).evictions += 1
        self._get_stats(namespace).size = len(store)

    @staticmethod
    def _now_ns() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1e9)
