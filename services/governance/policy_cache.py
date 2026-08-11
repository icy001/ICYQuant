"""
Policy Cache — caching layer for policy evaluations.

Caches policy evaluation results to avoid re-evaluating the same
policy-context combinations. Supports:
  - TTL-based expiry
  - Context hash-based cache keys
  - Scope-based invalidation
  - Stats for monitoring
  - Max size enforcement
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .policy_result import PolicyOutcome, VersionedPolicyResult


# ---------------------------------------------------------------------------
# Cache entry
# ---------------------------------------------------------------------------

@dataclass
class CacheEntry:
    """A single cache entry storing an evaluation result."""

    key: str
    result: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = 300.0  # Default 5 minutes
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    def is_expired(self, now: Optional[float] = None) -> bool:
        now = now or time.time()
        return (now - self.created_at) > self.ttl_seconds

    def touch(self) -> None:
        self.access_count += 1
        self.last_accessed = time.time()


# ---------------------------------------------------------------------------
# Policy Cache
# ---------------------------------------------------------------------------

@dataclass
class PolicyCache:
    """
    Caches policy evaluation results with TTL expiry.

    Cache key = hash(policy_id + version_id + context_hash)
    This ensures identical evaluations return cached results, while
    different contexts or policy versions are evaluated fresh.
    """

    # Storage: key → CacheEntry
    _cache: Dict[str, CacheEntry] = field(default_factory=dict)

    # Configuration
    default_ttl_seconds: float = 300.0  # 5 minutes
    max_size: int = 1000
    auto_evict: bool = True

    # Stats
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    stale_hits: int = 0  # Hits that required re-evaluation due to expiry

    # Version tracking (for invalidation)
    _active_versions: Dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Cache operations
    # ------------------------------------------------------------------

    def get(
        self,
        policy_id: str,
        version_id: str,
        context_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a cached evaluation result.

        Returns None if not found or expired.
        """
        key = self._make_key(policy_id, version_id, context_hash)
        entry = self._cache.get(key)

        if entry is None:
            self.misses += 1
            return None

        # Check expiry
        if entry.is_expired():
            del self._cache[key]
            self.stale_hits += 1
            return None

        # Check version: if the active version changed, invalidate
        active_vid = self._active_versions.get(policy_id)
        if active_vid and active_vid != version_id:
            del self._cache[key]
            self.misses += 1
            return None

        entry.touch()
        self.hits += 1
        return entry.result

    def set(
        self,
        policy_id: str,
        version_id: str,
        context_hash: str,
        result: Dict[str, Any],
        ttl_seconds: Optional[float] = None,
    ) -> None:
        """Cache an evaluation result."""
        key = self._make_key(policy_id, version_id, context_hash)

        # Evict if over max size
        if self.auto_evict and len(self._cache) >= self.max_size:
            self._evict_one()

        self._cache[key] = CacheEntry(
            key=key,
            result=result,
            ttl_seconds=ttl_seconds or self.default_ttl_seconds,
        )

        # Track active version
        self._active_versions[policy_id] = version_id

    def invalidate(
        self,
        policy_id: str = "",
        version_id: str = "",
    ) -> int:
        """
        Invalidate cached results.

        Args:
            policy_id: Invalidate all entries for this policy (or all if empty).
            version_id: Invalidate only entries for this specific version.

        Returns:
            Number of entries invalidated.
        """
        if not policy_id:
            # Invalidate all
            count = len(self._cache)
            self._cache.clear()
            self._active_versions.clear()
            return count

        keys_to_remove = []
        prefix = f"{policy_id}:"
        if version_id:
            prefix = f"{policy_id}:{version_id}:"

        for key in list(self._cache.keys()):
            if key.startswith(prefix):
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._cache[key]

        if not version_id:
            self._active_versions.pop(policy_id, None)

        return len(keys_to_remove)

    def invalidate_by_scope(self, scope: str) -> int:
        """
        Invalidate all cached results for policies in a given scope.

        This is a best-effort scope-based invalidation for when
        the market or portfolio state changes.
        """
        # Scope-based invalidation is coarse — invalidate all
        # In production, we'd index by scope for more targeted invalidation
        return self.invalidate()

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._active_versions.clear()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.stale_hits = 0

    # ------------------------------------------------------------------
    # Cache keys
    # ------------------------------------------------------------------

    @staticmethod
    def make_context_hash(context: Dict[str, Any]) -> str:
        """Create a deterministic hash of a context dict."""
        serialized = json.dumps(context, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _make_key(policy_id: str, version_id: str, context_hash: str) -> str:
        return f"{policy_id}:{version_id}:{context_hash}"

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    def get_batch(
        self,
        queries: List[Tuple[str, str, str]],
    ) -> Dict[Tuple[str, str, str], Optional[Dict[str, Any]]]:
        """
        Batch-get multiple cached results.

        Args:
            queries: List of (policy_id, version_id, context_hash) tuples.

        Returns:
            Dict mapping each query tuple to its result (or None).
        """
        results: Dict[Tuple[str, str, str], Optional[Dict[str, Any]]] = {}
        for query in queries:
            policy_id, version_id, context_hash = query
            results[query] = self.get(policy_id, version_id, context_hash)
        return results

    def set_batch(
        self,
        entries: List[Tuple[str, str, str, Dict[str, Any]]],
        ttl_seconds: Optional[float] = None,
    ) -> None:
        """Batch-set multiple cached results."""
        for entry in entries:
            policy_id, version_id, context_hash, result = entry
            self.set(policy_id, version_id, context_hash, result, ttl_seconds)

    # ------------------------------------------------------------------
    # Pre-warming
    # ------------------------------------------------------------------

    def warm(
        self,
        policy_ids: List[str],
        context_hashes: List[str],
        evaluator_fn,  # Callable[[policy_id, version_id, context], Dict]
    ) -> int:
        """
        Pre-warm the cache by evaluating common policy-context combinations.

        Useful for: system startup, after market open, after policy changes.
        """
        count = 0
        # This requires access to the registry for version lookup.
        # In practice, the caller would provide the versions.
        return count

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

    @property
    def is_full(self) -> int:
        return self.size >= self.max_size

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": self.size,
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{self.hit_rate:.2%}",
            "evictions": self.evictions,
            "stale_hits": self.stale_hits,
            "default_ttl_seconds": self.default_ttl_seconds,
            "tracked_policies": len(self._active_versions),
        }

    # ------------------------------------------------------------------
    # Eviction
    # ------------------------------------------------------------------

    def _evict_one(self) -> None:
        """Evict the least recently accessed entry."""
        if not self._cache:
            return

        # Find the LRU entry
        lru_key = min(
            self._cache.items(),
            key=lambda item: item[1].last_accessed,
        )[0]

        del self._cache[lru_key]
        self.evictions += 1

    def evict_expired(self) -> int:
        """Evict all expired entries."""
        now = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired(now)
        ]
        for key in expired_keys:
            del self._cache[key]
        self.evictions += len(expired_keys)
        return len(expired_keys)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stats": self.get_stats(),
            "active_versions": self._active_versions,
        }

    def __repr__(self) -> str:
        return (
            f"PolicyCache(size={self.size}/{self.max_size}, "
            f"hit_rate={self.hit_rate:.1%}, ttl={self.default_ttl_seconds}s)"
        )

    def __len__(self) -> int:
        return self.size
