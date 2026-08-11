"""
Data Index — multi-type indexes for accelerating data lake queries
with B-tree, bitmap, and hash indexes.

Commit 16 Part 1.3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class IndexType(str, Enum):
    BTREE = "btree"
    HASH = "hash"
    BITMAP = "bitmap"
    INVERTED = "inverted"
    BLOOM = "bloom"


@dataclass
class IndexEntry:
    key: Any
    file_path: str
    row_group: int = 0
    offset: int = 0
    min_value: Any = None
    max_value: Any = None
    row_count: int = 0


class DataIndex:
    """
    Abstract index for accelerating data lake queries.

    Supports multiple index types for different query patterns:
    - B-tree: Range queries on ordered columns
    - Hash: Point lookups
    - Bitmap: Low-cardinality columns
    - Inverted: Full-text search
    - Bloom: Existence checks
    """

    def __init__(self, name: str, index_type: IndexType, column: str) -> None:
        self.name = name
        self.index_type = index_type
        self.column = column
        self._entries: list[IndexEntry] = []
        self._built = False
        self.created_at = datetime.now(timezone.utc)

    async def insert(self, entry: IndexEntry) -> None:
        """Insert an entry into the index."""
        self._entries.append(entry)

    async def lookup(self, key: Any) -> list[IndexEntry]:
        """Look up entries by key."""
        return [e for e in self._entries if e.key == key]

    async def range_scan(
        self, start: Any, end: Any
    ) -> list[IndexEntry]:
        """Range scan between start and end."""
        return [
            e for e in self._entries
            if e.key is not None and start <= e.key <= end
        ]

    async def exists(self, key: Any) -> bool:
        """Check if key exists in index."""
        return any(e.key == key for e in self._entries)

    async def build(self) -> None:
        """Build/optimize the index."""
        self._entries.sort(key=lambda e: str(e.key) if e.key is not None else "")
        self._built = True
        logger.info("Index built: %s (%d entries)", self.name, len(self._entries))

    async def size(self) -> int:
        """Get the number of entries."""
        return len(self._entries)

    @property
    def is_built(self) -> bool:
        return self._built


class IndexManager:
    """
    Manages multiple indexes across datasets for query acceleration.

    Features:
    - Index creation and deletion
    - Automatic index selection for queries
    - Index statistics
    - Incremental index updates
    """

    def __init__(self) -> None:
        self._indexes: dict[str, dict[str, DataIndex]] = {}

    async def create_index(
        self,
        dataset: str,
        column: str,
        index_type: IndexType = IndexType.BTREE,
        name: Optional[str] = None,
    ) -> DataIndex:
        """Create an index on a dataset column."""
        index_name = name or f"idx_{dataset}_{column}"
        index = DataIndex(name=index_name, index_type=index_type, column=column)
        self._indexes.setdefault(dataset, {})[index_name] = index
        logger.info("Created index: %s (%s on %s)", index_name, index_type.value, column)
        return index

    async def get_index(self, dataset: str, name: str) -> Optional[DataIndex]:
        """Get an index by name."""
        return self._indexes.get(dataset, {}).get(name)

    async def get_best_index(
        self, dataset: str, column: str, query_type: str = "eq"
    ) -> Optional[DataIndex]:
        """Select the best index for a query pattern."""
        dataset_indexes = self._indexes.get(dataset, {})
        candidates = [idx for idx in dataset_indexes.values() if idx.column == column]
        if not candidates:
            return None
        return candidates[0]

    async def list_indexes(self, dataset: str) -> list[dict[str, Any]]:
        """List all indexes for a dataset."""
        return [
            {
                "name": idx.name,
                "type": idx.index_type.value,
                "column": idx.column,
                "entries": len(idx._entries),
                "built": idx.is_built,
            }
            for idx in self._indexes.get(dataset, {}).values()
        ]

    async def delete_index(self, dataset: str, name: str) -> bool:
        """Delete an index."""
        indexes = self._indexes.get(dataset, {})
        if name in indexes:
            del indexes[name]
            logger.info("Deleted index: %s", name)
            return True
        return False
