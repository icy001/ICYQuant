"""
Feature Store Adapter — Connects Strategy Platform to the Feature Store.

Provides standardized interface for fetching features, feature vectors,
and feature metadata needed by production strategies.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class FeatureRequest:
    """Request for feature data."""
    strategy_id: str
    feature_names: list[str]
    instruments: Optional[list[str]] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    as_of: Optional[datetime] = None
    max_lag_seconds: float = 300.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FeatureResult:
    """Result from feature store query."""
    request_id: str
    features: dict[str, Any] = field(default_factory=dict)  # feature_name -> values
    feature_metadata: dict[str, Any] = field(default_factory=dict)
    fetch_latency_ms: float = 0.0
    cache_hit: bool = False
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class FeatureStoreAdapter:
    """
    Adapter for the Feature Store subsystem.

    Provides async interface for feature retrieval with caching,
    batching, and latency tracking.

    Usage::

        adapter = FeatureStoreAdapter()
        await adapter.initialize()
        result = await adapter.fetch_features(FeatureRequest(
            strategy_id="strat_001",
            feature_names=["momentum_20d", "rsi_14d"],
            instruments=["AAPL", "GOOGL"],
        ))
    """

    def __init__(self) -> None:
        self._feature_cache: dict[str, dict[str, Any]] = {}
        self._request_count: int = 0
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the feature store adapter."""
        self._initialized = True
        logger.info("FeatureStoreAdapter initialized.")

    async def stop(self) -> None:
        """Stop the adapter."""
        self._initialized = False
        logger.info("FeatureStoreAdapter stopped.")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def fetch_features(self, request: FeatureRequest) -> FeatureResult:
        """Fetch features for a strategy."""
        self._request_count += 1
        request_id = f"feat_{self._request_count:06d}"

        start = asyncio.get_event_loop().time()

        # Check cache
        cache_key = f"{request.strategy_id}:{','.join(sorted(request.feature_names))}"
        cache_hit = cache_key in self._feature_cache

        if cache_hit:
            features = self._feature_cache[cache_key]
        else:
            # Simulate feature store fetch
            features = {name: {"status": "available", "source": "feature_store"} for name in request.feature_names}
            self._feature_cache[cache_key] = features

        latency = (asyncio.get_event_loop().time() - start) * 1000

        logger.debug(f"Features fetched: {len(request.feature_names)} features, cache={cache_hit}")
        return FeatureResult(
            request_id=request_id,
            features=features,
            fetch_latency_ms=latency,
            cache_hit=cache_hit,
        )

    async def get_feature_metadata(self, feature_name: str) -> Optional[dict[str, Any]]:
        """Get metadata for a specific feature."""
        return {
            "name": feature_name,
            "source": "feature_store",
            "status": "available",
        }

    async def invalidate_cache(self, strategy_id: Optional[str] = None) -> None:
        """Invalidate cached features."""
        if strategy_id:
            keys_to_remove = [k for k in self._feature_cache if k.startswith(strategy_id)]
            for k in keys_to_remove:
                del self._feature_cache[k]
        else:
            self._feature_cache.clear()
        logger.info(f"Feature cache invalidated: {strategy_id or 'all'}")

    async def health_check(self) -> dict[str, Any]:
        """Check adapter health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "cache_entries": len(self._feature_cache),
            "requests_served": self._request_count,
        }
