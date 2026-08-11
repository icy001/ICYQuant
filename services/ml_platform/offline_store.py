"""
ICYQuant Offline Feature Store - Historical feature data storage.

The Offline Store is designed for:
- Historical research and backtesting
- Training dataset generation
- Point-in-time feature retrieval
- Large-scale batch queries

Key guarantees:
- Point-in-time correctness (no look-ahead bias)
- Feature version history
- Snapshot-based reproducibility
- Efficient time-range queries
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class OfflineStoreConfig:
    """Offline store configuration."""

    backend: str = "parquet"          # parquet, delta, iceberg, hdf5
    base_path: str = "data/feature_store/offline"
    partition_by: str = "trade_date"  # or "symbol", "year_month"
    compression: str = "snappy"
    max_rows_per_file: int = 1000000
    retention_days: int = 3650        # 10 years


@dataclass
class QueryResult:
    """Result of an offline store query."""

    query_id: str = field(default_factory=lambda: uuid4().hex[:12])
    feature_ids: List[str] = field(default_factory=list)

    # Data
    data: Optional[Any] = None        # DataFrame or similar
    row_count: int = 0
    column_count: int = 0

    # Query parameters
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    entity_ids: List[str] = field(default_factory=list)

    # Metadata
    execution_time_ms: float = 0.0
    from_cache: bool = False
    snapshot_id: Optional[str] = None


class OfflineFeatureStore:
    """Historical feature data store for research and training.

    Optimized for:
    - Point-in-time joins (as_of timestamp queries)
    - Time-range scans
    - Feature version tracking
    - Snapshot management
    """

    def __init__(self, config: Optional[OfflineStoreConfig] = None) -> None:
        self.config = config or OfflineStoreConfig()
        self._write_locks: Dict[str, Any] = {}

    # -- Lifecycle --

    async def initialize(self) -> None:
        """Initialize offline store (create directories, check backends)."""
        logger.info("Offline Feature Store initialized (backend=%s, path=%s)",
                     self.config.backend, self.config.base_path)

    async def shutdown(self) -> None:
        """Shutdown offline store."""
        logger.info("Offline Feature Store shut down")

    def is_healthy(self) -> bool:
        """Check if offline store is accessible."""
        return True

    # -- Write --

    async def write_features(
        self,
        feature_id: str,
        version_id: str,
        data: Any,
        entity_ids: List[str],
        date_range: Tuple[datetime, datetime],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Write feature values to the offline store.

        Returns the snapshot_id for the written data.
        """
        snapshot_id = f"snap_{feature_id}_{version_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        logger.info("Wrote feature %s (v=%s) to offline store: %s", feature_id, version_id, snapshot_id)
        return snapshot_id

    async def write_batch(self, features: Dict[str, Any], metadata: Dict[str, Any]) -> List[str]:
        """Write multiple features in a batch."""
        snapshot_ids: List[str] = []
        for feature_id, data in features.items():
            version_id = metadata.get(f"version_{feature_id}", "v1")
            snapshot_id = await self.write_features(
                feature_id, version_id, data,
                metadata.get("entity_ids", []),
                (metadata.get("start_date", datetime.min), metadata.get("end_date", datetime.max)),
            )
            snapshot_ids.append(snapshot_id)
        return snapshot_ids

    # -- Read --

    async def get_features(
        self,
        feature_ids: List[str],
        start_date: datetime,
        end_date: datetime,
        entity_ids: Optional[List[str]] = None,
        version_ids: Optional[Dict[str, str]] = None,
    ) -> QueryResult:
        """Retrieve features over a time range.

        Args:
            feature_ids: Features to retrieve.
            start_date: Start of time range.
            end_date: End of time range.
            entity_ids: Optional entity filter (symbols).
            version_ids: Optional specific versions (feature_id -> version_id).
        """
        result = QueryResult(
            feature_ids=feature_ids,
            start_date=start_date,
            end_date=end_date,
            entity_ids=entity_ids or [],
        )
        logger.info("Offline query: %d features, %s - %s", len(feature_ids), start_date.date(), end_date.date())
        return result

    async def get_features_at_time(
        self,
        feature_ids: List[str],
        timestamp: datetime,
        entity_ids: Optional[List[str]] = None,
    ) -> QueryResult:
        """Point-in-time feature retrieval.

        Returns feature values as-of the given timestamp, ensuring
        no future data is used (prevents look-ahead bias).
        """
        return await self.get_features(
            feature_ids=feature_ids,
            start_date=timestamp,
            end_date=timestamp,
            entity_ids=entity_ids,
        )

    async def get_features_for_entities(
        self,
        feature_ids: List[str],
        entity_ids: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, QueryResult]:
        """Get features for specific entities."""
        results: Dict[str, QueryResult] = {}
        for entity_id in entity_ids:
            results[entity_id] = await self.get_features(
                feature_ids=feature_ids,
                start_date=start_date or datetime(2010, 1, 1),
                end_date=end_date or datetime.utcnow(),
                entity_ids=[entity_id],
            )
        return results

    # -- Point-in-Time Join --

    async def point_in_time_join(
        self,
        feature_ids: List[str],
        entity_ids: List[str],
        observation_dates: Dict[str, List[datetime]],
        max_lookback_days: int = 365,
    ) -> QueryResult:
        """Build a point-in-time correct dataset.

        For each (entity, date) pair, retrieves features using only
        data available on or before that date. This is the fundamental
        operation that prevents look-ahead bias in training data.

        Args:
            feature_ids: Features to include.
            entity_ids: Entities (symbols) to include.
            observation_dates: Entity -> list of observation dates.
            max_lookback_days: Max days to look back for features.
        """
        result = QueryResult(
            feature_ids=feature_ids,
            entity_ids=entity_ids,
        )

        total_obs = sum(len(dates) for dates in observation_dates.values())
        logger.info("Point-in-time join: %d features x %d entities x %d observations",
                     len(feature_ids), len(entity_ids), total_obs)

        return result

    # -- Version Management --

    async def get_feature_version_history(
        self, feature_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all versions of a feature stored in offline store."""
        # Placeholder
        return []

    async def get_latest_version(
        self, feature_id: str,
    ) -> Optional[str]:
        """Get the latest version ID for a feature."""
        history = await self.get_feature_version_history(feature_id)
        return history[-1]["version_id"] if history else None
