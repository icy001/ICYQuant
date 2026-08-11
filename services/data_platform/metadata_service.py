"""
ICYQuant Metadata Service.

Commit 16 Part 1.5 — Unified metadata management service.
Provides dataset-level metadata, column-level metadata, statistics,
and metadata search across the data platform.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ColumnMetadata:
    """Metadata for a dataset column."""
    name: str = ""
    data_type: str = ""
    nullable: bool = True
    description: str = ""
    is_partition_key: bool = False
    is_sort_key: bool = False
    statistics: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class DatasetMetadata:
    """Complete metadata for a dataset."""
    dataset_id: str = ""
    name: str = ""
    description: str = ""
    owner: str = ""
    domain: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    columns: list[ColumnMetadata] = field(default_factory=list)
    partition_columns: list[str] = field(default_factory=list)
    sort_columns: list[str] = field(default_factory=list)
    row_count: int = 0
    size_bytes: int = 0
    file_count: int = 0
    version_count: int = 0
    tags: list[str] = field(default_factory=list)
    custom_metadata: dict[str, Any] = field(default_factory=dict)


class MetadataService:
    """Unified metadata service.

    Provides:
      - Dataset metadata CRUD
      - Column-level metadata management
      - Metadata search and discovery
      - Statistics tracking
      - Custom metadata fields
    """

    def __init__(self, catalog: Any = None) -> None:
        self._catalog = catalog
        self._metadata: dict[str, DatasetMetadata] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Metadata CRUD
    # ------------------------------------------------------------------

    async def register(self, meta: DatasetMetadata) -> str:
        """Register dataset metadata."""
        async with self._lock:
            meta.updated_at = datetime.now(timezone.utc)
            if not meta.created_at:
                meta.created_at = meta.updated_at
            self._metadata[meta.dataset_id] = meta
        logger.info("Metadata registered for dataset: %s", meta.dataset_id)
        return meta.dataset_id

    async def get(self, dataset_id: str) -> Optional[DatasetMetadata]:
        """Get dataset metadata."""
        return self._metadata.get(dataset_id)

    async def update(self, dataset_id: str, **kwargs: Any) -> bool:
        """Update dataset metadata."""
        async with self._lock:
            meta = self._metadata.get(dataset_id)
            if not meta:
                return False
            for key, value in kwargs.items():
                if hasattr(meta, key):
                    setattr(meta, key, value)
            meta.updated_at = datetime.now(timezone.utc)
            return True

    async def delete(self, dataset_id: str) -> bool:
        """Delete dataset metadata."""
        async with self._lock:
            return self._metadata.pop(dataset_id, None) is not None

    # ------------------------------------------------------------------
    # Column Operations
    # ------------------------------------------------------------------

    async def add_column(self, dataset_id: str, col: ColumnMetadata) -> bool:
        """Add a column to dataset metadata."""
        meta = self._metadata.get(dataset_id)
        if not meta:
            return False
        meta.columns.append(col)
        meta.updated_at = datetime.now(timezone.utc)
        return True

    async def get_columns(self, dataset_id: str) -> list[ColumnMetadata]:
        """Get columns for a dataset."""
        meta = self._metadata.get(dataset_id)
        return list(meta.columns) if meta else []

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(self, keyword: str, limit: int = 20) -> list[DatasetMetadata]:
        """Search metadata by keyword."""
        kw = keyword.lower()
        results = []
        for meta in self._metadata.values():
            if (kw in meta.name.lower()
                    or kw in meta.description.lower()
                    or any(kw in tag.lower() for tag in meta.tags)):
                results.append(meta)
                if len(results) >= limit:
                    break
        return results

    async def list_all(self) -> list[DatasetMetadata]:
        """List all metadata entries."""
        return list(self._metadata.values())

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    async def update_statistics(
        self, dataset_id: str, row_count: int, size_bytes: int, **kwargs: Any,
    ) -> bool:
        """Update dataset statistics."""
        meta = self._metadata.get(dataset_id)
        if not meta:
            return False
        meta.row_count = row_count
        meta.size_bytes = size_bytes
        meta.updated_at = datetime.now(timezone.utc)
        return True

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def count(self) -> int:
        return len(self._metadata)
