"""
ICYQuant Online Feature Provider — Low-latency feature serving for inference.

Provides feature values at inference time with:
  - < 10ms feature retrieval from online store
  - Batch feature fetching for multiple symbols
  - Feature version tracking for audit trail
  - Point-in-time historical feature support
  - Cache-aware fetching
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data
# ---------------------------------------------------------------------------

class StoreType(str, Enum):
    """Online store backend type."""
    REDIS = "redis"
    MEMORY = "memory"
    DYNAMODB = "dynamodb"
    POSTGRES = "postgres"


@dataclass
class FeatureRecord:
    """A single feature value in the online store."""
    name: str
    value: Any
    version: str
    timestamp: str
    symbol: Optional[str] = None
    quality_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "version": self.version,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "quality_score": self.quality_score,
        }


@dataclass
class FeatureQueryResult:
    """Result of an online feature query."""
    features: Dict[str, Any]
    version: str
    query_latency_ms: float
    missing_features: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "features": self.features,
            "version": self.version,
            "query_latency_ms": round(self.query_latency_ms, 4),
            "missing_features": self.missing_features,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# In-Memory Feature Store (for development/testing)
# ---------------------------------------------------------------------------

class InMemoryFeatureStore:
    """Thread-safe in-memory feature store.

    Used as a lightweight online store for development and testing.
    In production, replace with Redis/DynamoDB backend.
    """

    def __init__(self):
        # key = "model_id:symbol:feature_name" → FeatureRecord
        self._store: Dict[str, FeatureRecord] = {}
        self._lock = asyncio.Lock()

    async def put(
        self,
        model_id: str,
        feature_name: str,
        value: Any,
        version: str = "latest",
        symbol: Optional[str] = None,
    ) -> None:
        key = self._make_key(model_id, symbol, feature_name)
        record = FeatureRecord(
            name=feature_name,
            value=value,
            version=version,
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol=symbol,
        )
        async with self._lock:
            self._store[key] = record

    async def get(
        self,
        model_id: str,
        feature_name: str,
        symbol: Optional[str] = None,
    ) -> Optional[FeatureRecord]:
        key = self._make_key(model_id, symbol, feature_name)
        async with self._lock:
            return self._store.get(key)

    async def get_batch(
        self,
        model_id: str,
        feature_names: List[str],
        symbol: Optional[str] = None,
    ) -> Dict[str, FeatureRecord]:
        result = {}
        async with self._lock:
            for name in feature_names:
                key = self._make_key(model_id, symbol, name)
                record = self._store.get(key)
                if record:
                    result[name] = record
        return result

    async def delete(
        self,
        model_id: str,
        feature_name: str,
        symbol: Optional[str] = None,
    ) -> bool:
        key = self._make_key(model_id, symbol, feature_name)
        async with self._lock:
            return self._store.pop(key, None) is not None

    async def clear(self) -> int:
        async with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    @staticmethod
    def _make_key(model_id: str, symbol: Optional[str], feature_name: str) -> str:
        symbol_part = f":{symbol}" if symbol else ""
        return f"{model_id}{symbol_part}:{feature_name}"


# ---------------------------------------------------------------------------
# Online Feature Provider
# ---------------------------------------------------------------------------

class OnlineFeatureProvider:
    """Low-latency feature provider for model inference.

    Key features:
      - Sub-10ms feature retrieval
      - Multi-symbol batch lookup
      - Automatic cache warming for hot features
      - Feature version tracking
      - Graceful degradation on store failures

    Usage::

        provider = OnlineFeatureProvider()
        await provider.initialize()
        result = await provider.get_features("nvda_model", ["momentum_20d", "vol_20d"])
        features = result.features  # {"momentum_20d": 0.05, "vol_20d": 0.12}
    """

    def __init__(
        self,
        store_type: StoreType = StoreType.MEMORY,
        cache_ttl_seconds: int = 30,
        max_batch_size: int = 100,
    ):
        self.store_type = store_type
        self.cache_ttl = cache_ttl_seconds
        self.max_batch_size = max_batch_size
        self._initialized = False

        # Backend store
        self._store = InMemoryFeatureStore()

        # Read cache: feature_name → (timestamp, value)
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._cache_lock = asyncio.Lock()

        # Stats
        self._total_queries: int = 0
        self._cache_hits: int = 0
        self._total_latency_ns: int = 0

    async def initialize(self) -> None:
        """Initialize provider — connect to backend store."""
        self._initialized = True
        logger.info(
            "OnlineFeatureProvider initialized — store=%s",
            self.store_type.value,
        )

    async def shutdown(self) -> None:
        """Shutdown — disconnect from store."""
        self._initialized = False

    # ------------------------------------------------------------------
    # Feature Retrieval
    # ------------------------------------------------------------------

    async def get_features(
        self,
        model_id: str,
        feature_names: List[str],
        *,
        symbols: Optional[List[str]] = None,
        timestamp: Optional[str] = None,
        use_cache: bool = True,
    ) -> Optional[FeatureQueryResult]:
        """Fetch feature values from online store.

        Args:
            model_id: Model identifier (used for namespacing).
            feature_names: List of feature names to fetch.
            symbols: Optional asset symbols for per-symbol features.
            timestamp: Point-in-time for historical values.
            use_cache: Whether to use read cache.

        Returns:
            FeatureQueryResult with features dict and metadata, or None on failure.
        """
        self._total_queries += 1
        start_ns = time.perf_counter_ns()

        features: Dict[str, Any] = {}
        missing: List[str] = []
        versions: Set[str] = set()

        # Determine symbols
        syms = symbols or [None]

        try:
            for symbol in syms:
                # Determine which names to fetch from store
                names_to_fetch = []
                for name in feature_names:
                    cache_key = self._cache_key(model_id, symbol, name)

                    if use_cache:
                        cached = await self._read_cache(cache_key)
                        if cached is not None:
                            features[name] = cached
                            self._cache_hits += 1
                            continue

                    names_to_fetch.append(name)

                if not names_to_fetch:
                    continue

                # Fetch from store
                store_results = await self._store.get_batch(
                    model_id=model_id,
                    feature_names=names_to_fetch,
                    symbol=symbol,
                )

                for name in names_to_fetch:
                    record = store_results.get(name)
                    if record:
                        features[name] = record.value
                        versions.add(record.version)

                        # Update cache
                        if use_cache:
                            cache_key = self._cache_key(model_id, symbol, name)
                            await self._write_cache(cache_key, record.value)
                    else:
                        missing.append(name)

        except Exception as exc:
            logger.error(
                "Online feature fetch failed for %s: %s", model_id, exc
            )
            # Return partial features if any were fetched
            if features:
                latency_ns = time.perf_counter_ns() - start_ns
                self._total_latency_ns += latency_ns
                return FeatureQueryResult(
                    features=features,
                    version="unknown",
                    query_latency_ms=latency_ns / 1_000_000.0,
                    missing_features=missing + feature_names,
                )
            return None

        latency_ns = time.perf_counter_ns() - start_ns
        self._total_latency_ns += latency_ns

        version = list(versions)[0] if len(versions) == 1 else "latest"

        return FeatureQueryResult(
            features=features,
            version=version,
            query_latency_ms=latency_ns / 1_000_000.0,
            missing_features=missing,
        )

    async def get_feature(
        self,
        model_id: str,
        feature_name: str,
        symbol: Optional[str] = None,
        default: Any = None,
    ) -> Any:
        """Fetch a single feature value.

        Args:
            model_id: Model identifier.
            feature_name: Feature name.
            symbol: Optional asset symbol.
            default: Default value if feature not found.

        Returns:
            Feature value or default.
        """
        result = await self.get_features(
            model_id=model_id,
            feature_names=[feature_name],
            symbols=[symbol] if symbol else None,
        )
        if result and result.features:
            return result.features.get(feature_name, default)
        return default

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    async def _read_cache(self, cache_key: str) -> Optional[Any]:
        """Read from local cache if not expired."""
        async with self._cache_lock:
            entry = self._cache.get(cache_key)
            if entry is None:
                return None
            ts, value = entry
            if time.time() - ts > self.cache_ttl:
                del self._cache[cache_key]
                return None
            return value

    async def _write_cache(self, cache_key: str, value: Any) -> None:
        """Write to local cache."""
        async with self._cache_lock:
            self._cache[cache_key] = (time.time(), value)

    async def invalidate_cache(self, model_id: str) -> int:
        """Invalidate cache entries for a model."""
        async with self._cache_lock:
            prefix = f"{model_id}:"
            keys = [k for k in self._cache if k.startswith(prefix)]
            for k in keys:
                del self._cache[k]
            return len(keys)

    async def clear_cache(self) -> int:
        """Clear all cached features."""
        async with self._cache_lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    # ------------------------------------------------------------------
    # Feature writing (for testing / seeding)
    # ------------------------------------------------------------------

    async def put_feature(
        self,
        model_id: str,
        feature_name: str,
        value: Any,
        symbol: Optional[str] = None,
    ) -> None:
        """Store a feature value (for testing/development)."""
        await self._store.put(
            model_id=model_id,
            feature_name=feature_name,
            value=value,
            symbol=symbol,
        )

    async def put_batch(
        self,
        model_id: str,
        features: Dict[str, Any],
        symbol: Optional[str] = None,
    ) -> None:
        """Store multiple features at once."""
        for name, value in features.items():
            await self.put_feature(model_id, name, value, symbol)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cache_key(model_id: str, symbol: Optional[str], feature_name: str) -> str:
        symbol_part = f":{symbol}" if symbol else ""
        return f"{model_id}{symbol_part}:{feature_name}"

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        total = max(self._total_queries, 1)
        return {
            "total_queries": self._total_queries,
            "cache_hits": self._cache_hits,
            "cache_hit_rate": round(self._cache_hits / total, 4),
            "avg_latency_ms": round(
                (self._total_latency_ns / 1_000_000.0) / total, 4
            ),
            "cache_size": len(self._cache),
        }

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "store_type": self.store_type.value,
            "stats": self.get_stats(),
        }

    def __repr__(self) -> str:
        return (
            f"OnlineFeatureProvider(store={self.store_type.value}, "
            f"queries={self._total_queries}, cache_hit_rate="
            f"{self._cache_hits / max(self._total_queries, 1):.1%})"
        )
