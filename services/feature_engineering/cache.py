"""Feature Cache.

Incremental computation cache to avoid re-computing features
that haven't changed. Supports time-based and hash-based
invalidation policies.

Usage::

    from services.feature_engineering import FeatureCache

    cache = FeatureCache()
    cache.put("ema20", "2024-01-01", [1.0, 2.0, 3.0])
    cached = cache.get("ema20", "2024-01-01")
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class CachePolicy(str, Enum):
    """Cache invalidation policy."""

    TTL = "ttl"                 # time-to-live based expiration
    HASH = "hash"               # hash-based invalidation
    VERSION = "version"         # version-based invalidation
    ALWAYS = "always"           # always use cache (never expire)
    NEVER = "never"             # never cache


@dataclass
class CacheEntry:
    """A single cache entry.

    Attributes:
        key: Unique cache key.
        values: Cached feature values.
        metadata: Arbitrary metadata.
        created_at: Timestamp of cache creation.
        ttl: Time-to-live in seconds (for TTL policy).
        version: Version tag (for VERSION policy).
        data_hash: SHA256 hash of values (for HASH policy).
    """

    key: str
    values: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    ttl: Optional[float] = None
    version: str = ""
    data_hash: str = ""

    def is_expired(self, now: Optional[float] = None) -> bool:
        """Check if TTL has elapsed."""
        if self.ttl is None:
            return False
        now = now or time.time()
        return (now - self.created_at) > self.ttl

    def __repr__(self) -> str:
        return f"CacheEntry(key={self.key!r}, n={len(self.values)})"


class FeatureCache:
    """Incremental computation cache for feature engineering.

    Avoids re-computing features whose input data hasn't changed.
    Supports multiple invalidation policies and cache statistics.

    Example::

        cache = FeatureCache(policy=CachePolicy.HASH, ttl=86400)

        # Store computed feature
        cache.put("ema20_daily", "2024-01-01", values, version="v2")

        # Check cache
        if cache.has("ema20_daily", "2024-01-01", version="v2"):
            values = cache.get("ema20_daily", "2024-01-01")
    """

    def __init__(
        self,
        policy: CachePolicy = CachePolicy.TTL,
        ttl: float = 86400,
        max_entries: int = 10000,
        default_version: str = "v1",
    ) -> None:
        self.policy = policy
        self.ttl = ttl
        self.max_entries = max_entries
        self.default_version = default_version
        self._store: Dict[str, CacheEntry] = {}
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

    # ---- Cache operations ----

    def get(self, feature_name: str, partition_key: str) -> Optional[List[float]]:
        """Retrieve cached feature values.

        Args:
            feature_name: Feature identifier.
            partition_key: Partition/date key.

        Returns:
            Cached values or None if not found/expired.
        """
        key = self._make_key(feature_name, partition_key)
        entry = self._store.get(key)

        if entry is None:
            self._misses += 1
            return None

        # Check policy
        if self.policy == CachePolicy.NEVER:
            self._misses += 1
            return None

        if self.policy == CachePolicy.TTL and entry.is_expired():
            del self._store[key]
            self._misses += 1
            return None

        self._hits += 1
        return entry.values

    def put(
        self,
        feature_name: str,
        partition_key: str,
        values: List[float],
        version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[float] = None,
    ) -> None:
        """Store feature values in the cache.

        Args:
            feature_name: Feature identifier.
            partition_key: Partition/date key.
            values: Feature values to cache.
            version: Version tag for VERSION policy.
            metadata: Optional metadata.
            ttl: Custom TTL override.
        """
        if self.policy == CachePolicy.NEVER:
            return

        key = self._make_key(feature_name, partition_key)
        data_hash = self._compute_hash(values)
        version = version or self.default_version

        entry = CacheEntry(
            key=key,
            values=list(values),
            metadata=metadata or {},
            created_at=time.time(),
            ttl=ttl or self.ttl,
            version=version,
            data_hash=data_hash,
        )

        # Evict if at capacity
        if len(self._store) >= self.max_entries and key not in self._store:
            self._evict_one()

        self._store[key] = entry

    def has(self, feature_name: str, partition_key: str, version: Optional[str] = None) -> bool:
        """Check if a valid cache entry exists.

        Args:
            feature_name: Feature identifier.
            partition_key: Partition/date key.
            version: Optional version to check against VERSION policy.

        Returns:
            True if a non-expired entry exists.
        """
        key = self._make_key(feature_name, partition_key)
        entry = self._store.get(key)
        if entry is None:
            return False

        if self.policy == CachePolicy.NEVER:
            return False

        if self.policy == CachePolicy.TTL and entry.is_expired():
            return False

        if self.policy == CachePolicy.VERSION and version and entry.version != version:
            return False

        return True

    def invalidate(self, feature_name: Optional[str] = None, partition_key: Optional[str] = None) -> int:
        """Invalidate cache entries.

        Args:
            feature_name: If provided, invalidate only this feature.
            partition_key: If provided, invalidate only this partition.

        Returns:
            Number of entries invalidated.
        """
        if feature_name is None and partition_key is None:
            count = len(self._store)
            self._store.clear()
            return count

        to_remove: List[str] = []
        prefix = f"{feature_name}:" if feature_name else ""

        for key in list(self._store.keys()):
            if prefix and not key.startswith(prefix):
                continue
            if partition_key and not key.endswith(f":{partition_key}"):
                continue
            to_remove.append(key)

        for key in to_remove:
            del self._store[key]

        return len(to_remove)

    # ---- New data detection ----

    def get_new_partitions(
        self,
        feature_name: str,
        all_partitions: List[str],
    ) -> List[str]:
        """Return partitions that are not yet cached.

        Useful for incremental computation: only compute features
        for new partitions.

        Args:
            feature_name: Feature identifier.
            all_partitions: All available partition keys.

        Returns:
            List of partition keys not in cache.
        """
        return [
            p for p in all_partitions
            if not self.has(feature_name, p)
        ]

    # ---- Statistics ----

    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0-1)."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        """Number of cached entries."""
        return len(self._store)

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        return {
            "size": self.size,
            "max_entries": self.max_entries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 4),
            "evictions": self._evictions,
            "policy": self.policy.value,
            "ttl": self.ttl,
        }

    # ---- Internal ----

    def _make_key(self, feature_name: str, partition_key: str) -> str:
        """Create a composite cache key."""
        return f"{feature_name}:{partition_key}"

    def _compute_hash(self, values: List[float]) -> str:
        """Compute SHA256 hash of feature values."""
        data = ",".join(f"{v:.6f}" for v in values[:100])  # sample first 100
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _evict_one(self) -> None:
        """Evict the oldest entry (LRU-like via created_at)."""
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda k: self._store[k].created_at)
        del self._store[oldest_key]
        self._evictions += 1

    # ---- Cleanup ----

    def cleanup_expired(self) -> int:
        """Remove all TTL-expired entries. Returns count removed."""
        now = time.time()
        expired = [k for k, e in self._store.items() if e.is_expired(now)]
        for k in expired:
            del self._store[k]
        return len(expired)

    def clear(self) -> None:
        """Clear the entire cache."""
        self._store.clear()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def __repr__(self) -> str:
        return (
            f"FeatureCache(policy={self.policy.value}, "
            f"size={self.size}/{self.max_entries}, "
            f"hit_rate={self.hit_rate:.1%})"
        )
