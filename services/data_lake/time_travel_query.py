"""
Time Travel Query — query datasets as they existed at any point in time,
leveraging versioned storage and snapshots.

Commit 16 Part 1.3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TimeTravelConfig:
    default_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    max_history_days: int = 365
    resolution: str = "millisecond"  # millisecond, second, minute
    fallback_to_latest: bool = True


@dataclass
class TemporalView:
    dataset: str
    as_of: datetime
    version_id: str
    snapshot_id: Optional[str] = None
    is_latest: bool = False
    record_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TimeTravelQuery:
    """
    Query datasets as they existed at any historical point in time.

    Features:
    - Point-in-time queries (AS OF timestamp)
    - Version-range queries (BETWEEN two versions)
    - Snapshot-based queries
    - Automatic version resolution
    - Fallback to latest when history unavailable
    """

    def __init__(
        self,
        storage: Any = None,
        catalog: Any = None,
        versions: Any = None,
        config: Optional[TimeTravelConfig] = None,
    ) -> None:
        self._storage = storage
        self._catalog = catalog
        self._versions = versions
        self.config = config or TimeTravelConfig()

    async def query_as_of(
        self,
        dataset: str,
        as_of: datetime,
        *,
        filters: Optional[dict[str, Any]] = None,
        limit: int = 10_000,
    ) -> list[Any]:
        """
        Query a dataset as it existed at a specific point in time.

        Args:
            dataset: Dataset name.
            as_of: Point in time to query.
            filters: Optional query filters.
            limit: Maximum records to return.

        Returns:
            Records as they existed at `as_of`.
        """
        # Resolve the version that was current at `as_of`
        version = await self._resolve_version(dataset, as_of)
        if not version:
            if self.config.fallback_to_latest:
                logger.warning(
                    "No version at %s for %s, falling back to latest",
                    as_of.isoformat(), dataset,
                )
                version = await self._versions.get_latest(dataset) if self._versions else None
            if not version:
                return []

        logger.info(
            "Time travel query: %s AS OF %s → version %s",
            dataset, as_of.isoformat(), version.version_id,
        )

        # Query storage for the resolved version
        results: list[Any] = []
        if self._storage:
            results = await self._storage.read(
                f"datasets/{dataset}/version={version.version_id}",
                filters=filters,
                limit=limit,
            )

        return results

    async def query_between(
        self,
        dataset: str,
        start: datetime,
        end: datetime,
        *,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Query dataset changes between two points in time.
        Returns versions that existed in the range.
        """
        versions = await self._versions.list_versions(dataset) if self._versions else []
        matching = []
        for v in versions:
            created = datetime.fromisoformat(v["created_at"]) if isinstance(v["created_at"], str) else v["created_at"]
            if start <= created <= end:
                matching.append(v)

        return [
            {
                "version_id": v["version_id"],
                "record_count": v.get("record_count", 0),
                "created_at": v["created_at"],
            }
            for v in matching
        ]

    async def _resolve_version(
        self, dataset: str, as_of: datetime
    ) -> Optional[Any]:
        """Resolve which version was active at the given timestamp."""
        if not self._versions:
            return None

        all_versions = await self._versions.list_versions(dataset)

        # Find the version whose created_at <= as_of and is closest
        best_version = None
        for v in all_versions:
            created = v.get("created_at")
            if isinstance(created, str):
                created = datetime.fromisoformat(created)
            if isinstance(created, datetime) and created <= as_of:
                if best_version is None or created > best_version[0]:
                    best_version = (created, v)

        if best_version:
            return await self._versions.get(dataset, best_version[1]["version_id"])
        return None

    async def get_temporal_view(
        self, dataset: str, as_of: datetime
    ) -> TemporalView:
        """Get a temporal view description for a point-in-time query."""
        version = await self._resolve_version(dataset, as_of)
        return TemporalView(
            dataset=dataset,
            as_of=as_of,
            version_id=version.version_id if version else "latest",
            is_latest=version is None,
        )
