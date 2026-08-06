"""Feature Store — unified storage for raw and processed features with versioning.

Architecture::

    Raw Feature → Processed Feature → Version → Cache

Supports offline and online read paths for training and inference.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class FeatureStoreState(str, Enum):
    UNINITIALIZED = "uninitialized"
    READY = "ready"
    CLOSED = "closed"


@dataclass
class FeatureRecord:
    """A single feature record in the store."""

    feature_id: str
    name: str
    feature_type: str
    values: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: int = 1
    status: str = "raw"  # raw, processed, cached
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class FeatureStore:
    """Unified feature storage with versioning and caching.

    Responsibilities:
    * Store raw and processed features
    * Version control for feature evolution
    * Cache frequently accessed features
    * Support offline (batch) and online (point-in-time) reads
    """

    def __init__(self) -> None:
        self._state = FeatureStoreState.UNINITIALIZED
        self._features: Dict[str, FeatureRecord] = {}
        self._feature_versions: Dict[str, List[FeatureRecord]] = {}
        self._cache: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._store_id = str(uuid4())

    @property
    def state(self) -> FeatureStoreState:
        return self._state

    async def initialize(self) -> None:
        async with self._lock:
            self._state = FeatureStoreState.READY
            logger.info("FeatureStore %s initialized", self._store_id)

    async def close(self) -> None:
        async with self._lock:
            self._features.clear()
            self._cache.clear()
            self._state = FeatureStoreState.CLOSED

    # ── feature storage ───────────────────────────────────────────────────

    async def put(
        self,
        name: str,
        values: Dict[str, float],
        feature_type: str = "raw",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FeatureRecord:
        """Store a feature."""
        async with self._lock:
            feature_id = str(uuid4())
            record = FeatureRecord(
                feature_id=feature_id,
                name=name,
                feature_type=feature_type,
                values=values,
                metadata=metadata or {},
                status="raw",
            )
            self._features[feature_id] = record
            self._feature_versions.setdefault(name, []).append(record)
            logger.debug("Feature %s stored: %s", feature_id, name)
            return record

    async def get(self, feature_id: str) -> Optional[FeatureRecord]:
        return self._features.get(feature_id)

    async def get_by_name(self, name: str, version: Optional[int] = None) -> Optional[FeatureRecord]:
        versions = self._feature_versions.get(name, [])
        if not versions:
            return None
        if version is not None:
            for v in versions:
                if v.version == version:
                    return v
            return None
        return versions[-1]  # latest version

    async def list_features(
        self,
        feature_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[FeatureRecord]:
        results = list(self._features.values())
        if feature_type:
            results = [f for f in results if f.feature_type == feature_type]
        if status:
            results = [f for f in results if f.status == status]
        return results

    async def update_status(
        self, feature_id: str, new_status: str
    ) -> Optional[FeatureRecord]:
        async with self._lock:
            record = self._features.get(feature_id)
            if record is None:
                return None
            record.status = new_status
            record.updated_at = datetime.now(timezone.utc)
            return record

    async def version_feature(self, name: str) -> Optional[FeatureRecord]:
        """Create a new version snapshot of the latest feature."""
        async with self._lock:
            latest = await self.get_by_name(name)
            if latest is None:
                return None
            new_version = FeatureRecord(
                feature_id=str(uuid4()),
                name=name,
                feature_type=latest.feature_type,
                values=dict(latest.values),
                metadata=dict(latest.metadata),
                version=latest.version + 1,
                status="processed",
            )
            self._features[new_version.feature_id] = new_version
            self._feature_versions.setdefault(name, []).append(new_version)
            return new_version

    # ── cache ─────────────────────────────────────────────────────────────

    async def cache_put(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._cache[key] = {
            "value": value,
            "ttl": ttl,
            "cached_at": datetime.now(timezone.utc),
        }

    async def cache_get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry["ttl"] is not None:
            elapsed = (datetime.now(timezone.utc) - entry["cached_at"]).total_seconds()
            if elapsed > entry["ttl"]:
                del self._cache[key]
                return None
        return entry["value"]

    async def cache_invalidate(self, key: Optional[str] = None) -> None:
        if key is None:
            self._cache.clear()
        else:
            self._cache.pop(key, None)

    # ── stats ─────────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        return {
            "total_features": len(self._features),
            "unique_names": len(self._feature_versions),
            "cached_entries": len(self._cache),
            "state": self._state.value,
        }
