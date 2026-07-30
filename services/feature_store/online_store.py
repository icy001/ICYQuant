"""Online Feature Store — low-latency feature serving for real-time inference.

Provides millisecond-level feature retrieval for live trading
and online prediction. Backed by in-memory cache (with Redis
support in the infrastructure layer).

Usage::

    from services.feature_store import OnlineFeatureStore, OnlineFeatureRecord

    store = OnlineFeatureStore()
    store.set("NVDA", {"ema20": 182.31, "atr14": 4.82})
    features = store.get("NVDA")  # {"ema20": 182.31, "atr14": 4.82}
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StoreTTL(str, Enum):
    """Time-to-live presets for online feature records."""

    REALTIME = "realtime"  # 5 seconds (tick-level)
    SHORT = "short"        # 1 minute
    MEDIUM = "medium"      # 1 hour
    LONG = "long"          # 24 hours


# TTL values in seconds
_TTL_MAP: Dict[StoreTTL, int] = {
    StoreTTL.REALTIME: 5,
    StoreTTL.SHORT: 60,
    StoreTTL.MEDIUM: 3600,
    StoreTTL.LONG: 86400,
}


@dataclass
class OnlineFeatureRecord:
    """A single feature record in the online store.

    Attributes:
        entity_id: Entity identifier (e.g. symbol, account_id).
        features: Feature name -> value mapping.
        ttl: Time-to-live category.
        created_at: Unix timestamp.
        expires_at: Unix timestamp of expiration.
        metadata: Arbitrary metadata.
    """

    entity_id: str
    features: Dict[str, float] = field(default_factory=dict)
    ttl: StoreTTL = StoreTTL.MEDIUM
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    metadata: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.expires_at == 0.0:
            ttl_seconds = _TTL_MAP.get(self.ttl, 3600)
            self.expires_at = self.created_at + ttl_seconds

    def is_expired(self) -> bool:
        """Check if this record has expired."""
        return time.time() > self.expires_at


class OnlineFeatureStore:
    """Low-latency feature store for real-time inference.

    Provides set/get/delete operations for feature vectors keyed
    by entity ID, with TTL-based expiration.
    """

    # ---- 分组：初始化 ----

    def __init__(self, default_ttl: StoreTTL = StoreTTL.MEDIUM) -> None:
        """Initialize the online store.

        Args:
            default_ttl: Default TTL for new records.
        """
        self.default_ttl = default_ttl
        self._store: Dict[str, OnlineFeatureRecord] = {}
        self._feature_index: Dict[str, List[str]] = {}  # feature_name -> [entity_ids]

    # ---- 分组：写入 ----

    def set(
        self,
        entity_id: str,
        features: Dict[str, float],
        ttl: Optional[StoreTTL] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> OnlineFeatureRecord:
        """Set feature values for an entity.

        Args:
            entity_id: Entity identifier (e.g. symbol).
            features: Feature name -> value mapping.
            ttl: Optional TTL override.
            metadata: Optional metadata.

        Returns:
            The stored OnlineFeatureRecord.
        """
        ttl_value = ttl or self.default_ttl
        record = OnlineFeatureRecord(
            entity_id=entity_id,
            features=dict(features),
            ttl=ttl_value,
            metadata=metadata or {},
        )
        self._store[entity_id] = record

        # Update feature index
        for fname in features:
            self._feature_index.setdefault(fname, [])
            if entity_id not in self._feature_index[fname]:
                self._feature_index[fname].append(entity_id)

        return record

    def update(
        self,
        entity_id: str,
        features: Dict[str, float],
    ) -> Optional[OnlineFeatureRecord]:
        """Update (merge) feature values for an existing entity.

        Args:
            entity_id: Entity identifier.
            features: Feature values to merge.

        Returns:
            Updated record, or None if entity not found.
        """
        record = self._store.get(entity_id)
        if record is None:
            return None

        record.features.update(features)
        record.created_at = time.time()
        ttl_seconds = _TTL_MAP.get(record.ttl, 3600)
        record.expires_at = record.created_at + ttl_seconds

        # Update index
        for fname in features:
            self._feature_index.setdefault(fname, [])
            if entity_id not in self._feature_index[fname]:
                self._feature_index[fname].append(entity_id)

        return record

    # ---- 分组：读取 ----

    def get(self, entity_id: str) -> Optional[Dict[str, float]]:
        """Get feature values for an entity.

        Args:
            entity_id: Entity identifier.

        Returns:
            Feature dict or None if not found or expired.
        """
        record = self._store.get(entity_id)
        if record is None:
            return None
        if record.is_expired():
            self._remove_from_index(entity_id, record)
            del self._store[entity_id]
            return None
        return dict(record.features)

    def get_feature(self, entity_id: str, feature_name: str) -> Optional[float]:
        """Get a single feature value for an entity.

        Args:
            entity_id: Entity identifier.
            feature_name: Feature name.

        Returns:
            Feature value or None.
        """
        features = self.get(entity_id)
        if features is None:
            return None
        return features.get(feature_name)

    def batch_get(self, entity_ids: List[str]) -> Dict[str, Dict[str, float]]:
        """Get features for multiple entities.

        Args:
            entity_ids: List of entity identifiers.

        Returns:
            Dict of entity_id -> feature_dict. Missing entities are excluded.
        """
        result: Dict[str, Dict[str, float]] = {}
        for eid in entity_ids:
            features = self.get(eid)
            if features is not None:
                result[eid] = features
        return result

    def get_entities_with_feature(self, feature_name: str) -> List[str]:
        """Get all entity IDs that have a specific feature.

        Args:
            feature_name: Feature name.

        Returns:
            Sorted list of entity IDs.
        """
        return sorted(self._feature_index.get(feature_name, []))

    # ---- 分组：删除 ----

    def delete(self, entity_id: str) -> bool:
        """Delete an entity's feature record.

        Args:
            entity_id: Entity identifier.

        Returns:
            True if deleted, False if not found.
        """
        record = self._store.pop(entity_id, None)
        if record is None:
            return False
        self._remove_from_index(entity_id, record)
        return True

    def delete_feature(self, entity_id: str, feature_name: str) -> bool:
        """Delete a single feature from an entity.

        Args:
            entity_id: Entity identifier.
            feature_name: Feature name.

        Returns:
            True if deleted, False if not found.
        """
        record = self._store.get(entity_id)
        if record is None:
            return False
        if feature_name in record.features:
            del record.features[feature_name]
            if entity_id in self._feature_index.get(feature_name, []):
                self._feature_index[feature_name].remove(entity_id)
            return True
        return False

    # ---- 分组：维护 ----

    def expire(self) -> int:
        """Remove all expired records.

        Returns:
            Number of records removed.
        """
        expired_ids = [
            eid for eid, record in self._store.items() if record.is_expired()
        ]
        for eid in expired_ids:
            record = self._store[eid]
            self._remove_from_index(eid, record)
            del self._store[eid]
        return len(expired_ids)

    def clear(self) -> None:
        """Clear all records."""
        self._store.clear()
        self._feature_index.clear()

    # ---- 分组：统计 ----

    def entity_count(self) -> int:
        """Return current entity count (excluding expired)."""
        self.expire()
        return len(self._store)

    def feature_count(self) -> int:
        """Return unique feature name count in index."""
        return len(self._feature_index)

    # ---- 分组：内部 ----

    def _remove_from_index(self, entity_id: str, record: OnlineFeatureRecord) -> None:
        """Remove entity from all feature index entries."""
        for fname in record.features:
            if fname in self._feature_index and entity_id in self._feature_index[fname]:
                self._feature_index[fname].remove(entity_id)
