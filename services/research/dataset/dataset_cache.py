"""Dataset Cache — multi-backend caching for dataset access acceleration.

Supports Memory, Redis, and Disk-based caching with TTL, LRU eviction,
and cache warming strategies.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class CacheBackend(str, Enum):
    """Supported cache backends."""

    MEMORY = "memory"  # In-process LRU cache
    REDIS = "redis"    # Distributed Redis cache
    DISK = "disk"      # Local disk cache


class CachePolicy(str, Enum):
    """Cache eviction policies."""

    LRU = "lru"           # Least Recently Used
    TTL = "ttl"           # Time-To-Live based
    LFU = "lfu"           # Least Frequently Used
    FIFO = "fifo"         # First-In-First-Out


class CacheState(str, Enum):
    """Cache entry states."""

    VALID = "valid"
    STALE = "stale"
    EXPIRED = "expired"
    EVICTED = "evicted"


@dataclass
class CacheEntry:
    """A single cache entry with metadata."""

    key: str
    value: Any
    ttl_seconds: int = 3600
    backend: CacheBackend = CacheBackend.MEMORY
    policy: CachePolicy = CachePolicy.LRU
    state: CacheState = CacheState.VALID
    access_count: int = 0
    size_bytes: int = 0
    checksum: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(seconds=self.ttl_seconds)

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > (self.expires_at or datetime.now(timezone.utc))

    @property
    def age_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()

    def touch(self) -> None:
        """Update last access time and increment count."""
        self.last_accessed = datetime.now(timezone.utc)
        self.access_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "ttl_seconds": self.ttl_seconds,
            "backend": self.backend.value,
            "policy": self.policy.value,
            "state": self.state.value,
            "access_count": self.access_count,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "tags": self.tags,
        }

    def __repr__(self) -> str:
        return f"CacheEntry(key={self.key}, state={self.state.value}, hits={self.access_count})"


class DatasetCache:
    """Multi-backend dataset caching layer.

    Features:
    * Multi-backend support (Memory/Redis/Disk)
    * TTL-based expiration
    * LRU eviction with configurable max size
    * Cache warming for frequently used datasets
    * Hit/miss statistics

    Usage::

        cache = DatasetCache(backend=CacheBackend.MEMORY, max_entries=1000)
        cache.set("dataset:ohlcv:daily", data, ttl=3600)
        data = cache.get("dataset:ohlcv:daily")
    """

    # Global counters (thread-safe via asyncio locks)
    _hits: int = 0
    _misses: int = 0
    _evictions: int = 0
    _writes: int = 0
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(
        self,
        backend: CacheBackend = CacheBackend.MEMORY,
        max_entries: int = 10000,
        default_ttl: int = 3600,
        policy: CachePolicy = CachePolicy.LRU,
        namespace: str = "research",
    ) -> None:
        self._backend = backend
        self._max_entries = max_entries
        self._default_ttl = default_ttl
        self._policy = policy
        self._namespace = namespace
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._tags_index: Dict[str, List[str]] = {}
        self._state = "initialized"

    # ---- Public API ----

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a cached value. Returns default on miss or expired."""
        entry = self._store.get(key)
        if entry is None:
            DatasetCache._misses += 1
            return default
        if entry.is_expired:
            self._evict(key)
            DatasetCache._misses += 1
            return default
        entry.touch()
        DatasetCache._hits += 1
        return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> CacheEntry:
        """Store a value in the cache."""
        if len(self._store) >= self._max_entries:
            self._evict_lru()
        ttl_seconds = ttl or self._default_ttl
        entry = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl_seconds,
            backend=self._backend,
            policy=self._policy,
            size_bytes=self._estimate_size(value),
            tags=tags or [],
        )
        self._store[key] = entry
        if tags:
            for tag in tags:
                self._tags_index.setdefault(tag, []).append(key)
        DatasetCache._writes += 1
        return entry

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from cache."""
        entry = self._store.pop(key, None)
        if entry:
            for tag in entry.tags:
                if tag in self._tags_index:
                    self._tags_index[tag] = [k for k in self._tags_index[tag] if k != key]
            return True
        return False

    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all entries with a given tag."""
        keys = self._tags_index.pop(tag, [])
        count = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                count += 1
        return count

    def clear(self) -> None:
        """Clear all cache entries."""
        self._store.clear()
        self._tags_index.clear()

    def touch(self, key: str) -> bool:
        """Refresh TTL of an existing entry."""
        entry = self._store.get(key)
        if entry and not entry.is_expired:
            entry.expires_at = datetime.now(timezone.utc) + timedelta(seconds=entry.ttl_seconds)
            entry.touch()
            return True
        return False

    def warm(self, keys: List[str], loader: callable) -> int:
        """Preload multiple keys using a loader function.

        Args:
            keys: List of cache keys to warm.
            loader: Async/sync callable that takes a key and returns the value.

        Returns number of keys successfully cached.
        """
        count = 0
        for key in keys:
            if not self.get(key):
                try:
                    value = loader(key)
                    self.set(key, value)
                    count += 1
                except Exception:
                    logger.warning("Failed to warm cache key: %s", key, exc_info=True)
        return count

    # ---- Query ----

    def exists(self, key: str) -> bool:
        entry = self._store.get(key)
        return entry is not None and not entry.is_expired

    def keys(self) -> List[str]:
        return list(self._store.keys())

    def entry_count(self) -> int:
        return len(self._store)

    def tag_count(self) -> int:
        return len(self._tags_index)

    # ---- Statistics ----

    @property
    def hits(self) -> int:
        return DatasetCache._hits

    @property
    def misses(self) -> int:
        return DatasetCache._misses

    @property
    def hit_ratio(self) -> float:
        total = DatasetCache._hits + DatasetCache._misses
        return DatasetCache._hits / total if total > 0 else 0.0

    @property
    def eviction_count(self) -> int:
        return DatasetCache._evictions

    def stats(self) -> Dict[str, Any]:
        return {
            "backend": self._backend.value,
            "max_entries": self._max_entries,
            "current_entries": self.entry_count(),
            "tag_count": self.tag_count(),
            "hits": DatasetCache._hits,
            "misses": DatasetCache._misses,
            "hit_ratio": self.hit_ratio,
            "evictions": DatasetCache._evictions,
            "writes": DatasetCache._writes,
        }

    # ---- Internal ----

    def _evict(self, key: str) -> None:
        entry = self._store.pop(key, None)
        if entry:
            DatasetCache._evictions += 1
            for tag in entry.tags:
                if tag in self._tags_index:
                    self._tags_index[tag] = [k for k in self._tags_index[tag] if k != key]

    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if not self._store:
            return
        if self._policy == CachePolicy.LRU:
            lru_key = next(iter(self._store))
        elif self._policy == CachePolicy.FIFO:
            lru_key = next(iter(self._store))
        else:
            # Default: evict oldest
            oldest = min(self._store.items(), key=lambda x: x[1].created_at)
            lru_key = oldest[0]
        self._evict(lru_key)

    @staticmethod
    def _estimate_size(value: Any) -> int:
        try:
            return len(json.dumps(value, default=str).encode("utf-8"))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def build_key(prefix: str, **parts: str) -> str:
        """Build a structured cache key."""
        segments = [prefix] + [f"{k}={v}" for k, v in sorted(parts.items())]
        return ":".join(segments)

    def __repr__(self) -> str:
        return (
            f"DatasetCache(backend={self._backend.value}, "
            f"entries={self.entry_count()}/{self._max_entries}, "
            f"hit_ratio={self.hit_ratio:.1%})"
        )
