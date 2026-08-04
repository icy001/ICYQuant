"""
Configuration cache.

Provides in-memory caching for configuration
values with TTL (time-to-live) and LRU
(least-recently-used) eviction.

Features:
- TTL-based expiration
- LRU eviction when max_size reached
- Thread-safe operations
- Hit/miss statistics
- Snapshot caching

Usage:
    cache = ConfigurationCache(ttl=300, max_size=1000)
    cache.put("server.port", 8080)
    value = cache.get("server.port")  # 8080
    # After 300 seconds:
    value = cache.get("server.port")  # None (expired)
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from .constants import DEFAULT_CACHE_MAX_SIZE, DEFAULT_CACHE_TTL
from .snapshot import ConfigurationSnapshot, SnapshotStore


class CacheEntry:
    """A single cache entry with timestamp."""

    __slots__ = ("value", "timestamp", "hits")

    def __init__(
        self,
        value: Any,
        timestamp: float,
    ) -> None:
        self.value = value
        self.timestamp = timestamp
        self.hits = 0

    def is_expired(
        self,
        ttl: int,
    ) -> bool:
        """Check if entry is expired."""

        if ttl <= 0:
            return False
        return (time.time() - self.timestamp) > ttl


class ConfigurationCache:
    """
    Configuration cache with TTL and LRU eviction.

    Provides fast access to configuration values
    with automatic expiration and size management.

    Features:
    - TTL: Entries expire after configured seconds
    - LRU: Least recently used entries evicted when full
    - Thread-safe: All operations protected by lock
    - Statistics: Tracks hits, misses, evictions
    - Snapshot support: Can cache entire snapshots

    Usage:
        cache = ConfigurationCache(ttl=300, max_size=1000)
        cache.put("key", value)
        value = cache.get("key")
        stats = cache.get_stats()
    """

    def __init__(
        self,
        ttl: int = DEFAULT_CACHE_TTL,
        max_size: int = DEFAULT_CACHE_MAX_SIZE,
    ) -> None:
        """
        Initialize cache.

        Args:
            ttl: Time-to-live in seconds (0 = no expiration).
            max_size: Maximum number of entries.
        """

        self._ttl = ttl
        self._max_size = max_size
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0

    @property
    def ttl(
        self,
    ) -> int:
        """Get TTL."""
        return self._ttl

    @property
    def max_size(
        self,
    ) -> int:
        """Get max size."""
        return self._max_size

    @property
    def size(
        self,
    ) -> int:
        """Get current cache size."""

        with self._lock:
            return len(self._cache)

    def get(
        self,
        key: str,
    ) -> Any:
        """
        Get a value from cache.

        Returns None if key not found or expired.
        Moves accessed entry to end (most recently used).

        Args:
            key: Cache key.

        Returns:
            Cached value or None.
        """

        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired(self._ttl):
                del self._cache[key]
                self._expirations += 1
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.hits += 1
            self._hits += 1
            return entry.value

    def put(
        self,
        key: str,
        value: Any,
    ) -> None:
        """
        Put a value into cache.

        If key already exists, updates value and
        moves to end. If cache is full, evicts
        least recently used entry.

        Args:
            key: Cache key.
            value: Value to cache.
        """

        with self._lock:
            # If key exists, update and move to end
            if key in self._cache:
                self._cache.move_to_end(key)

            # Evict LRU if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
                self._evictions += 1

            self._cache[key] = CacheEntry(
                value=value,
                timestamp=time.time(),
            )

    def exists(
        self,
        key: str,
    ) -> bool:
        """Check if key exists and is not expired."""

        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired(self._ttl):
                del self._cache[key]
                self._expirations += 1
                return False
            return True

    def delete(
        self,
        key: str,
    ) -> bool:
        """
        Delete a key from cache.

        Returns:
            True if key was present.
        """

        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(
        self,
    ) -> None:
        """Clear all cached entries."""

        with self._lock:
            self._cache.clear()

    def cleanup_expired(
        self,
    ) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed.
        """

        removed = 0
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired(self._ttl)
            ]
            for key in expired_keys:
                del self._cache[key]
                removed += 1
            self._expirations += removed
        return removed

    def get_stats(
        self,
    ) -> Dict[str, Any]:
        """Get cache statistics."""

        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total) if total > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl": self._ttl,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "expirations": self._expirations,
                "hit_rate": round(hit_rate, 4),
            }

    def keys(
        self,
    ) -> List[str]:
        """Get all cache keys."""

        with self._lock:
            return list(self._cache.keys())


class SnapshotCache:
    """
    Versioned snapshot cache.

    Caches ConfigurationSnapshot objects and provides
    atomic, thread-safe access to the current snapshot.

    Uses SnapshotStore internally for version management
    and rollback support.

    Usage:
        cache = SnapshotCache()
        snapshot = cache.update(values, environment="prod")
        current = cache.current
        cache.rollback(steps=1)
    """

    def __init__(
        self,
        max_history: int = 10,
    ) -> None:
        """Initialize snapshot cache."""
        self._store = SnapshotStore(max_history=max_history)

    @property
    def current(
        self,
    ) -> Optional[ConfigurationSnapshot]:
        """Get current snapshot (thread-safe)."""
        return self._store.current

    @property
    def version(
        self,
    ) -> int:
        """Get current version."""
        return self._store.version

    def update(
        self,
        values: Dict[str, Any],
        environment: str = "development",
        sources_used: Optional[List[str]] = None,
    ) -> ConfigurationSnapshot:
        """
        Update cache with new values.

        Atomically creates a new snapshot and
        swaps it in.

        Args:
            values: Configuration values.
            environment: Deployment environment.
            sources_used: Source names that contributed.

        Returns:
            New snapshot.
        """
        return self._store.update(values, environment, sources_used)

    def rollback(
        self,
        steps: int = 1,
    ) -> Optional[ConfigurationSnapshot]:
        """
        Rollback to a previous version.

        Args:
            steps: Number of versions to rollback.

        Returns:
            Restored snapshot or None.
        """
        return self._store.rollback(steps)

    def get_history(
        self,
    ) -> List[ConfigurationSnapshot]:
        """Get snapshot history."""
        return self._store.get_history()

    def clear_history(
        self,
    ) -> None:
        """Clear snapshot history."""
        self._store.clear_history()

    def get_stats(
        self,
    ) -> Dict[str, Any]:
        """Get cache statistics."""
        return self._store.get_stats()
