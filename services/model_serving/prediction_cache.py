"""
ICYQuant Prediction Cache — TTL-based prediction result cache.

Caches inference results to reduce redundant model computations.
Key use case: identical features for the same model within a short
time window should return the same cached prediction.

Features:
  - TTL-based expiration
  - LRU eviction under memory pressure
  - Per-model cache configuration
  - Cache statistics
  - Deterministic cache key generation
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CacheEntry:
    """A cached prediction result."""
    prediction: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at


# ---------------------------------------------------------------------------
# Prediction Cache
# ---------------------------------------------------------------------------

class PredictionCache:
    """TTL-based LRU prediction cache.

    Cache key = hash(model_id + version + sorted features).

    Usage::

        cache = PredictionCache(max_size=10000, ttl_seconds=60)
        await cache.initialize()

        result = await cache.get("nvda_model", "v2.1", features)
        if result is None:
            result = await inference_engine.predict(...)
            await cache.set("nvda_model", "v2.1", features, result)
    """

    def __init__(
        self,
        max_size: int = 10000,
        ttl_seconds: int = 60,
        enable_stats: bool = True,
    ):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.enable_stats = enable_stats

        # OrderedDict for LRU: oldest entries first
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()

        # Per-model TTL overrides
        self._model_ttls: Dict[str, int] = {}

        # Stats
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0
        self._expirations: int = 0

        # Background cleanup
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    async def initialize(self) -> None:
        """Initialize the cache and start background cleanup."""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("PredictionCache initialized — max_size=%d, ttl=%ds",
                    self.max_size, self.ttl_seconds)

    async def shutdown(self) -> None:
        """Shutdown the cache."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        async with self._lock:
            self._store.clear()
        logger.info("PredictionCache shutdown — %d entries cleared", len(self._store))

    # ------------------------------------------------------------------
    # Get / Set
    # ------------------------------------------------------------------

    async def get(
        self,
        model_id: str,
        version: str,
        features: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Get cached prediction if available and not expired.

        Args:
            model_id: Model identifier.
            version: Model version.
            features: Input feature dict.

        Returns:
            Cached prediction dict, or None.
        """
        cache_key = self._make_key(model_id, version, features)

        async with self._lock:
            entry = self._store.get(cache_key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired:
                del self._store[cache_key]
                self._expirations += 1
                self._misses += 1
                return None

            # Move to end (LRU: mark as recently used)
            self._store.move_to_end(cache_key)
            self._hits += 1
            return entry.prediction

    async def set(
        self,
        model_id: str,
        version: str,
        features: Dict[str, Any],
        prediction: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Store a prediction in the cache.

        Args:
            model_id: Model identifier.
            version: Model version.
            features: Input feature dict (used for key).
            prediction: Prediction result to cache.
            ttl_seconds: Override default TTL for this entry.
        """
        cache_key = self._make_key(model_id, version, features)
        ttl = ttl_seconds or self._model_ttls.get(model_id, self.ttl_seconds)

        entry = CacheEntry(
            prediction=prediction,
            expires_at=time.time() + ttl,
        )

        async with self._lock:
            # Evict oldest if at capacity
            if len(self._store) >= self.max_size and cache_key not in self._store:
                self._store.popitem(last=False)
                self._evictions += 1

            self._store[cache_key] = entry
            self._store.move_to_end(cache_key)

    async def invalidate(self, model_id: str, version: Optional[str] = None) -> int:
        """Invalidate cache entries for a model.

        Args:
            model_id: Model identifier.
            version: Optional specific version to invalidate.

        Returns:
            Number of entries invalidated.
        """
        prefix = f"{model_id}:{version}" if version else f"{model_id}:"
        async with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]
            return len(keys)

    async def clear(self) -> int:
        """Clear all cached predictions."""
        async with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    # ------------------------------------------------------------------
    # Per-model TTL
    # ------------------------------------------------------------------

    def set_model_ttl(self, model_id: str, ttl_seconds: int) -> None:
        """Set a custom TTL for a specific model."""
        self._model_ttls[model_id] = ttl_seconds

    def get_model_ttl(self, model_id: str) -> int:
        """Get TTL for a specific model (defaults to global TTL)."""
        return self._model_ttls.get(model_id, self.ttl_seconds)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        total = max(self._hits + self._misses, 1)
        return {
            "size": len(self._store),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 4),
            "evictions": self._evictions,
            "expirations": self._expirations,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(
        model_id: str,
        version: str,
        features: Dict[str, Any],
    ) -> str:
        """Create a deterministic cache key."""
        feature_str = json.dumps(features, sort_keys=True, default=str)
        feature_hash = hashlib.sha256(feature_str.encode()).hexdigest()[:16]
        return f"{model_id}:{version}:{feature_hash}"

    async def _cleanup_loop(self) -> None:
        """Background cleanup of expired entries."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Every 30 seconds
                async with self._lock:
                    expired_keys = [
                        k for k, v in self._store.items()
                        if v.is_expired
                    ]
                    for k in expired_keys:
                        del self._store[k]
                        self._expirations += 1
                    if expired_keys:
                        logger.debug("Cache cleanup: %d expired entries removed",
                                    len(expired_keys))
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Cache cleanup error")

    def __repr__(self) -> str:
        hit_rate = self._hits / max(self._hits + self._misses, 1)
        return (
            f"PredictionCache(size={len(self._store)}/{self.max_size}, "
            f"hit_rate={hit_rate:.1%})"
        )
