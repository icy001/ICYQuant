"""
ICYQuant Data Catalog.

Commit 16 Part 1.5 — Central data catalog for dataset discovery,
search, and metadata management. Provides a searchable registry of
all datasets available in the unified data platform.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CatalogEntryType(str, Enum):
    """Type of catalog entry."""
    DATASET = "dataset"
    TABLE = "table"
    VIEW = "view"
    STREAM = "stream"
    SNAPSHOT = "snapshot"
    INDEX = "index"


class DataDomain(str, Enum):
    """Data domain classification."""
    MARKET_DATA = "market_data"
    REFERENCE_DATA = "reference_data"
    FUNDAMENTAL = "fundamental"
    ALTERNATIVE = "alternative"
    RESEARCH = "research"
    RISK = "risk"
    EXECUTION = "execution"
    DERIVED = "derived"


class DataClassification(str, Enum):
    """Data sensitivity classification."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass
class CatalogEntry:
    """An entry in the data catalog."""
    dataset_id: str = ""
    name: str = ""
    description: str = ""
    entry_type: CatalogEntryType = CatalogEntryType.DATASET
    domain: DataDomain = DataDomain.MARKET_DATA
    classification: DataClassification = DataClassification.INTERNAL
    owner: str = ""
    stewards: list[str] = field(default_factory=list)
    schema_version: int = 1
    partition_key: str = "date"
    retention_days: int = 365
    row_count: int = 0
    size_bytes: int = 0
    last_updated: Optional[datetime] = None
    quality_score: float = 100.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchQuery:
    """A catalog search query."""
    keywords: str = ""
    domain: Optional[DataDomain] = None
    entry_type: Optional[CatalogEntryType] = None
    owner: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    min_quality_score: float = 0.0
    limit: int = 20
    offset: int = 0


@dataclass
class SearchResult:
    """Result of a catalog search."""
    query: str = ""
    entries: list[CatalogEntry] = field(default_factory=list)
    total_count: int = 0
    latency_ms: float = 0.0


class DataCatalog:
    """Central data catalog for dataset discovery and metadata.

    Provides:
      - Dataset registration and discovery
      - Full-text search across datasets
      - Domain-based browsing
      - Tag-based filtering
      - Quality score filtering
    """

    def __init__(self) -> None:
        self._entries: dict[str, CatalogEntry] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------------

    async def register(self, entry: CatalogEntry) -> str:
        """Register a dataset in the catalog."""
        async with self._lock:
            entry.last_updated = datetime.now(timezone.utc)
            self._entries[entry.dataset_id] = entry
        logger.info("Catalog entry registered: %s (%s)", entry.dataset_id, entry.name)
        return entry.dataset_id

    async def get(self, dataset_id: str) -> Optional[CatalogEntry]:
        """Get a catalog entry by dataset ID."""
        return self._entries.get(dataset_id)

    async def update(self, dataset_id: str, **kwargs: Any) -> bool:
        """Update a catalog entry."""
        async with self._lock:
            entry = self._entries.get(dataset_id)
            if not entry:
                return False
            for key, value in kwargs.items():
                if hasattr(entry, key):
                    setattr(entry, key, value)
            entry.last_updated = datetime.now(timezone.utc)
            return True

    async def delete(self, dataset_id: str) -> bool:
        """Remove a dataset from the catalog."""
        async with self._lock:
            return self._entries.pop(dataset_id, None) is not None

    # ------------------------------------------------------------------
    # Search & Discovery
    # ------------------------------------------------------------------

    async def search(self, query: SearchQuery) -> SearchResult:
        """Search the catalog."""
        start = datetime.now(timezone.utc)
        results: list[CatalogEntry] = []

        kw_lower = query.keywords.lower() if query.keywords else ""

        for entry in self._entries.values():
            # Filter by domain
            if query.domain and entry.domain != query.domain:
                continue
            # Filter by type
            if query.entry_type and entry.entry_type != query.entry_type:
                continue
            # Filter by owner
            if query.owner and entry.owner != query.owner:
                continue
            # Filter by quality
            if entry.quality_score < query.min_quality_score:
                continue
            # Filter by tags
            if query.tags:
                if not set(query.tags).intersection(entry.tags):
                    continue
            # Keyword match
            if kw_lower:
                if (kw_lower not in entry.name.lower()
                        and kw_lower not in entry.description.lower()
                        and not any(kw_lower in tag.lower() for tag in entry.tags)):
                    continue

            results.append(entry)

        total = len(results)
        results = results[query.offset:query.offset + query.limit]

        latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        return SearchResult(
            query=query.keywords,
            entries=results,
            total_count=total,
            latency_ms=latency,
        )

    async def list_by_domain(self, domain: DataDomain) -> list[CatalogEntry]:
        """List all entries in a domain."""
        return [e for e in self._entries.values() if e.domain == domain]

    async def list_by_type(self, entry_type: CatalogEntryType) -> list[CatalogEntry]:
        """List all entries of a type."""
        return [e for e in self._entries.values() if e.entry_type == entry_type]

    async def list_all(self) -> list[CatalogEntry]:
        """List all catalog entries."""
        return list(self._entries.values())

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def count(self) -> int:
        return len(self._entries)

    def domain_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self._entries.values():
            d = e.domain.value
            counts[d] = counts.get(d, 0) + 1
        return counts
