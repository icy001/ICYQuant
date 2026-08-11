"""
Metadata Catalog — centralized metadata store for all data lake assets
tracking schemas, statistics, storage locations, and ingestion history.

Commit 16 Part 1.3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DataStatistics:
    row_count: int = 0
    total_bytes: int = 0
    min_timestamp: Optional[datetime] = None
    max_timestamp: Optional[datetime] = None
    null_counts: dict[str, int] = field(default_factory=dict)
    distinct_counts: dict[str, int] = field(default_factory=dict)
    column_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class StorageLocation:
    path: str
    backend: str = "local"
    format: str = "parquet"
    partition: str = ""
    file_count: int = 0
    total_bytes: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CatalogEntry:
    dataset: str
    version_id: str
    storage_path: str
    statistics: DataStatistics = field(default_factory=DataStatistics)
    schema_hash: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: dict[str, str] = field(default_factory=dict)


class MetadataCatalog:
    """
    Centralized metadata catalog for the data lake.

    Tracks:
    - Dataset schemas and versions
    - Data statistics (row counts, byte sizes, timestamps)
    - Storage locations and formats
    - Ingestion history and lineage
    """

    def __init__(self, storage: Any = None, datasets: Any = None) -> None:
        self._storage = storage
        self._datasets = datasets
        self._entries: dict[str, list[CatalogEntry]] = {}
        self._statistics: dict[str, DataStatistics] = {}
        self._locations: dict[str, list[StorageLocation]] = {}

    async def register_ingestion(
        self,
        dataset: Any,
        version: Any,
        storage_path: str,
        record_count: int,
        partition: Optional[str] = None,
    ) -> CatalogEntry:
        """Register a successful ingestion event."""
        entry = CatalogEntry(
            dataset=dataset.name,
            version_id=version.version_id,
            storage_path=storage_path,
            statistics=DataStatistics(row_count=record_count),
        )

        if dataset.name not in self._entries:
            self._entries[dataset.name] = []
        self._entries[dataset.name].append(entry)

        location = StorageLocation(
            path=storage_path,
            partition=partition or "",
        )
        if dataset.name not in self._locations:
            self._locations[dataset.name] = []
        self._locations[dataset.name].append(location)

        logger.debug(
            "Catalog: registered ingestion for %s v%s (%d records)",
            dataset.name, version.version_id, record_count,
        )
        return entry

    async def get_statistics(self, dataset_name: str) -> dict[str, Any]:
        """Get aggregate statistics for a dataset."""
        stats = self._statistics.get(dataset_name, DataStatistics())
        entries = self._entries.get(dataset_name, [])
        total_rows = sum(e.statistics.row_count for e in entries)
        total_bytes = sum(e.statistics.total_bytes for e in entries)

        return {
            "dataset": dataset_name,
            "total_rows": total_rows,
            "total_bytes": total_bytes,
            "version_count": len(entries),
            "min_timestamp": stats.min_timestamp.isoformat() if stats.min_timestamp else None,
            "max_timestamp": stats.max_timestamp.isoformat() if stats.max_timestamp else None,
        }

    async def get_versions(self, dataset_name: str) -> list[dict[str, Any]]:
        """Get all versions for a dataset."""
        entries = self._entries.get(dataset_name, [])
        return [
            {
                "version_id": e.version_id,
                "storage_path": e.storage_path,
                "row_count": e.statistics.row_count,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ]

    async def get_latest_version(self, dataset_name: str) -> Optional[str]:
        """Get the latest version ID for a dataset."""
        entries = self._entries.get(dataset_name, [])
        if not entries:
            return None
        return max(entries, key=lambda e: e.created_at).version_id

    async def get_storage_locations(self, dataset_name: str) -> list[StorageLocation]:
        """Get all storage locations for a dataset."""
        return self._locations.get(dataset_name, [])

    async def update_statistics(
        self, dataset_name: str, stats: DataStatistics
    ) -> None:
        """Update statistics for a dataset."""
        self._statistics[dataset_name] = stats

    async def list_datasets(self) -> list[str]:
        """List all datasets in the catalog."""
        return list(self._entries.keys())
