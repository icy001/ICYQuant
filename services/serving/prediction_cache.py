"""Prediction Cache — reduce redundant inference computations.

Caches prediction results with TTL-based expiration. Multiple strategies
requesting the same symbol within the same tick window get cached results
instead of redundant model inference.

Usage::

    cache = PredictionCache(config=CacheConfig(ttl_seconds=5))
    cache.set("NVDA", 0.82, 0.93, "alpha_us")
    cached = cache.get("NVDA")  # returns CachedPrediction within TTL
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class CachePolicy(str, Enum):
    """Cache eviction/update policy."""
    TTL = "ttl"          # Time-to-live based expiration
    TICK_BASED = "tick"  # Invalidate on new tick (market data driven)
    LRU = "lru"          # Least recently used eviction
    ADAPTIVE = "adaptive"  # Dynamic TTL based on volatility
    NONE = "none"        # No caching


@dataclass
class CacheConfig:
    """Prediction cache configuration.

    Attributes:
        policy: Cache eviction policy.
        ttl_seconds: Default TTL for cached predictions.
        max_entries: Max entries in cache (LRU eviction).
        tick_ttl_seconds: TTL when tick_based policy.
        enable_stats: Track hit/miss statistics.
    """

    policy: CachePolicy = CachePolicy.TTL
    ttl_seconds: float = 5.0
    max_entries: int = 100000
    tick_ttl_seconds: float = 3.0
    enable_stats: bool = True


@dataclass
class CachedPrediction:
    """A cached prediction entry.

    Attributes:
        symbol: Entity symbol.
        prediction: Model prediction value.
        confidence: Prediction confidence [0,1].
        model_name: Model that produced prediction.
        cached_at: Timestamp when cached.
        expires_at: Expiration timestamp.
        access_count: How many times this entry was served.
    """

    symbol: str
    prediction: float
    confidence: Optional[float] = None
    model_name: str = ""
    cached_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    access_count: int = 1

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def age_seconds(self) -> float:
        return time.time() - self.cached_at

    def touch(self) -> None:
        self.access_count += 1


class PredictionCache:
    """In-memory prediction cache with TTL/LRU eviction.

    Reduces CPU/GPU load by serving repeated predictions for the same
    symbol within the cache TTL window.

    Usage::

        cache = PredictionCache(config=CacheConfig(ttl_seconds=5))
        cache.set("NVDA", 0.82, 0.93, model_name="alpha_us")
        result = cache.get("NVDA")  # returns CachedPrediction or None
        stats = cache.get_stats()   # {"hits": 142, "misses": 58, "hit_rate": 0.71}
    """

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self._store: Dict[str, CachedPrediction] = {}
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0
        self._last_tick: float = 0.0

    def get(self, symbol: str, model_name: Optional[str] = None) -> Optional[CachedPrediction]:
        """Get a cached prediction if exists and not expired.

        Args:
            symbol: Entity symbol.
            model_name: Optional model filter. If provided, only matches
                       predictions from this model.

        Returns:
            CachedPrediction or None.
        """
        # Check tick-based invalidation
        if self.config.policy == CachePolicy.TICK_BASED:
            if self._last_tick > 0 and (time.time() - self._last_tick) < self.config.tick_ttl_seconds:
                pass  # Within tick window
            else:
                self._misses += 1
                return None

        if model_name:
            # Exact key lookup
            key = self._make_key(symbol, model_name)
            entry = self._store.get(key)
        else:
            # Search all entries for this symbol (any model)
            prefix = f"{symbol}:"
            entry = None
            expired_keys = []
            for k, v in self._store.items():
                if k == symbol or k.startswith(prefix):
                    if not v.expired:
                        entry = v
                        break
                    else:
                        expired_keys.append(k)
            for k in expired_keys:
                del self._store[k]

        if entry is None:
            self._misses += 1
            return None

        if entry.expired:
            del self._store[key]
            self._misses += 1
            return None

        entry.touch()
        self._hits += 1
        return entry

    def set(
        self,
        symbol: str,
        prediction: float,
        confidence: Optional[float] = None,
        model_name: str = "",
    ) -> CachedPrediction:
        """Store a prediction in cache.

        Args:
            symbol: Entity symbol.
            prediction: Model prediction value.
            confidence: Prediction confidence.
            model_name: Model identifier.

        Returns:
            The newly cached entry.
        """
        # Evict if at capacity
        if len(self._store) >= self.config.max_entries:
            self._evict_lru()

        ttl = self.config.ttl_seconds
        now = time.time()

        entry = CachedPrediction(
            symbol=symbol,
            prediction=prediction,
            confidence=confidence,
            model_name=model_name,
            cached_at=now,
            expires_at=now + ttl,
        )

        key = self._make_key(symbol, model_name)
        self._store[key] = entry
        return entry

    def invalidate(self, symbol: str, model_name: Optional[str] = None) -> bool:
        """Invalidate (remove) a cached prediction.

        Args:
            symbol: Entity symbol.
            model_name: Optional model filter. If None, invalidates all
                       entries for this symbol.

        Returns:
            True if at least one entry was removed.
        """
        if model_name:
            key = self._make_key(symbol, model_name)
            if key in self._store:
                del self._store[key]
                return True
            return False

        removed = 0
        prefix = f"{symbol}:"
        keys = [k for k in self._store if k == symbol or k.startswith(prefix)]
        for k in keys:
            del self._store[k]
            removed += 1
        return removed > 0

    def invalidate_all(self) -> int:
        """Clear entire cache. Returns number of entries removed."""
        count = len(self._store)
        self._store.clear()
        return count

    def on_tick(self) -> None:
        """Notify cache of a new tick (for tick_based policy)."""
        self._last_tick = time.time()
        if self.config.policy == CachePolicy.TICK_BASED:
            self.invalidate_all()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "entries": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
            "evictions": self._evictions,
            "max_entries": self.config.max_entries,
            "policy": self.config.policy.value,
            "ttl_seconds": self.config.ttl_seconds,
        }

    def list_entries(self) -> List[CachedPrediction]:
        """List all cached entries (for debugging)."""
        return list(self._store.values())

    # ---- internal ----

    @staticmethod
    def _make_key(symbol: str, model_name: Optional[str] = None) -> str:
        if model_name:
            return f"{symbol}:{model_name}"
        return symbol

    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda k: self._store[k].cached_at)
        del self._store[oldest_key]
        self._evictions += 1
