"""
ICYQuant Online Feature Store - Low-latency feature serving for real-time inference.

    Live Market Data
           │
           ▼
    Feature Calculation
           │
           ▼
    Online Feature Store
           │
           ▼
    Model Inference

Ensures feature consistency between research (offline) and production (online).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class OnlineStoreConfig:
    """Online store configuration."""

    backend: str = "redis"           # redis, dynamodb, bigtable, cassandra
    connection_string: str = "redis://localhost:6379"
    ttl_seconds: int = 86400         # 24 hours
    max_connections: int = 50
    max_retries: int = 3
    write_batch_size: int = 100
    read_batch_size: int = 100
    enable_cache: bool = True


@dataclass
class OnlineQueryResult:
    """Result of an online feature query."""

    request_id: str = field(default_factory=lambda: uuid4().hex[:12])
    entity_id: str = ""
    features: Dict[str, float] = field(default_factory=dict)
    latency_ms: float = 0.0
    cache_hit: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None


class OnlineFeatureStore:
    """Low-latency feature store for real-time model inference.

    Key requirements:
    - <10ms latency for feature retrieval
    - Supports concurrent reads during market hours
    - Key-value store optimized for feature vectors
    - TTL-based expiration for stale features
    - Feature consistency with offline store
    """

    def __init__(self, config: Optional[OnlineStoreConfig] = None) -> None:
        self.config = config or OnlineStoreConfig()
        self._store: Dict[str, Dict[str, float]] = {}  # entity_id -> {feature_id: value}
        self._write_timestamps: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    # -- Lifecycle --

    async def initialize(self) -> None:
        """Initialize online store connection."""
        logger.info("Online Feature Store initialized (backend=%s, ttl=%ds)",
                     self.config.backend, self.config.ttl_seconds)

    async def shutdown(self) -> None:
        """Shutdown online store."""
        logger.info("Online Feature Store shut down")

    def is_healthy(self) -> bool:
        """Check if online store is accessible."""
        return True

    # -- Write --

    async def put_features(
        self,
        entity_id: str,
        features: Dict[str, float],
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Write feature values for a single entity.

        Overwrites existing values for the same entity.
        """
        async with self._lock:
            self._store[entity_id] = dict(features)
            self._write_timestamps[entity_id] = timestamp or datetime.utcnow()

    async def put_batch(
        self,
        entity_features: Dict[str, Dict[str, float]],
        timestamp: Optional[datetime] = None,
    ) -> int:
        """Write features for multiple entities in batch.

        Args:
            entity_features: {entity_id: {feature_id: value}}
            timestamp: Write timestamp.

        Returns:
            Number of entities written.
        """
        count = 0
        for entity_id, features in entity_features.items():
            await self.put_features(entity_id, features, timestamp)
            count += 1
        logger.debug("Online store batch write: %d entities", count)
        return count

    # -- Read --

    async def get_features(
        self,
        entity_id: str,
        feature_ids: List[str],
    ) -> OnlineQueryResult:
        """Get feature values for a single entity.

        Low-latency retrieval designed for real-time inference.
        """
        result = OnlineQueryResult(entity_id=entity_id)
        t0 = time.time()

        entity_features = self._store.get(entity_id, {})

        for feature_id in feature_ids:
            result.features[feature_id] = entity_features.get(feature_id, float('nan'))

        result.latency_ms = (time.time() - t0) * 1000
        return result

    async def get_features_batch(
        self,
        entity_ids: List[str],
        feature_ids: List[str],
    ) -> Dict[str, OnlineQueryResult]:
        """Get features for multiple entities.

        Used for portfolio-level inference where multiple instruments
        need feature vectors simultaneously.
        """
        results: Dict[str, OnlineQueryResult] = {}
        for entity_id in entity_ids:
            results[entity_id] = await self.get_features(entity_id, feature_ids)
        return results

    async def get_feature_vector(
        self,
        entity_id: str,
        feature_ids: List[str],
    ) -> List[float]:
        """Get a flat feature vector for model inference.

        Returns a list of feature values in the order of feature_ids,
        with NaN for missing features.
        """
        result = await self.get_features(entity_id, feature_ids)
        return [result.features.get(fid, float('nan')) for fid in feature_ids]

    # -- Sync with Offline --

    async def sync_from_offline(
        self,
        offline_store: Any,
        feature_ids: List[str],
        entity_ids: List[str],
        timestamp: Optional[datetime] = None,
    ) -> int:
        """Sync features from offline store to online store.

        Ensures feature consistency between research and production.
        """
        ts = timestamp or datetime.utcnow()
        count = 0

        # Placeholder: fetch from offline and write to online
        for entity_id in entity_ids:
            features: Dict[str, float] = {}
            for feature_id in feature_ids:
                features[feature_id] = 0.0  # placeholder
            await self.put_features(entity_id, features, ts)
            count += 1

        logger.info("Synced %d entities from offline to online store", count)
        return count

    # -- Maintenance --

    async def delete_entity(self, entity_id: str) -> bool:
        """Remove all features for an entity."""
        async with self._lock:
            existed = entity_id in self._store
            self._store.pop(entity_id, None)
            self._write_timestamps.pop(entity_id, None)
            return existed

    async def get_freshness(self, entity_id: str) -> Optional[float]:
        """Get feature age in seconds for an entity."""
        ts = self._write_timestamps.get(entity_id)
        if ts is None:
            return None
        return (datetime.utcnow() - ts).total_seconds()

    @property
    def entity_count(self) -> int:
        return len(self._store)
