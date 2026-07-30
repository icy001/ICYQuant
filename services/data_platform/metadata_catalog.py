"""ICYQuant Metadata Catalog.

Unified metadata management for all data assets in the platform.
Every dataset, feature, model, and pipeline has discoverable metadata:
    - Owner, description, tags
    - Schema, statistics, freshness
    - Lineage links (upstream/downstream)
    - Quality metrics
    - Access patterns

Usage::

    catalog = MetadataCatalog(CatalogConfig())
    catalog.register("market_tick", CatalogEntry(
        name="market_tick",
        entry_type=CatalogEntryType.DATASET,
        owner="Market Team",
        ...
    ))
    results = catalog.search("tick")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from services.data_platform.config import (
    CatalogConfig,
    CatalogEntryType,
    DataClassification,
)


# ============================================================================
# Catalog Types
# ============================================================================


@dataclass
class ColumnMetadata:
    """Metadata for a single column/field."""

    name: str
    data_type: str
    description: str = ""
    nullable: bool = True
    is_primary_key: bool = False
    is_partition_key: bool = False
    statistics: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class DatasetStatistics:
    """Statistics for a dataset."""

    row_count: int = 0
    size_bytes: int = 0
    null_count: Dict[str, int] = field(default_factory=dict)
    distinct_count: Dict[str, int] = field(default_factory=dict)
    min_values: Dict[str, Any] = field(default_factory=dict)
    max_values: Dict[str, Any] = field(default_factory=dict)
    last_updated: Optional[datetime] = None
    freshness_hours: float = 0.0


@dataclass
class CatalogEntry:
    """An entry in the metadata catalog.

    Represents any data asset: dataset, table, view, feature, model, etc.
    """

    name: str
    entry_type: CatalogEntryType
    description: str = ""
    owner: str = ""
    owner_team: str = ""
    classification: DataClassification = DataClassification.INTERNAL
    columns: List[ColumnMetadata] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    statistics: Optional[DatasetStatistics] = None
    source_system: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    is_deprecated: bool = False
    deprecation_message: str = ""
    custom_properties: Dict[str, Any] = field(default_factory=dict)
    lineage_upstream: List[str] = field(default_factory=list)
    lineage_downstream: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "entry_type": self.entry_type.value,
            "description": self.description,
            "owner": self.owner,
            "owner_team": self.owner_team,
            "classification": self.classification.value,
            "columns": [c.__dict__ for c in self.columns],
            "tags": self.tags,
            "labels": self.labels,
            "source_system": self.source_system,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "is_deprecated": self.is_deprecated,
            "deprecation_message": self.deprecation_message,
            "lineage_upstream": self.lineage_upstream,
            "lineage_downstream": self.lineage_downstream,
            "custom_properties": self.custom_properties,
        }


@dataclass
class SearchResult:
    """Result from a catalog search."""

    entries: List[CatalogEntry] = field(default_factory=list)
    total_matches: int = 0
    query: str = ""
    filters_applied: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Metadata Catalog
# ============================================================================


class MetadataCatalog:
    """Unified Metadata Catalog for ICYQuant.

    Provides registration, discovery, and search of all data assets
    across the platform. Every dataset, feature, model, and pipeline
    has discoverable metadata.

    Usage::

        catalog = MetadataCatalog(CatalogConfig())
        catalog.register("market_tick", entry)
        entry = catalog.get("market_tick")
        results = catalog.search("tick", entry_type=CatalogEntryType.DATASET)
    """

    def __init__(self, config: Optional[CatalogConfig] = None) -> None:
        self.config = config or CatalogConfig()
        self._entries: Dict[str, CatalogEntry] = {}
        self._index: Dict[str, Set[str]] = {}  # tag/type → entry names

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, name: str, entry: CatalogEntry) -> CatalogEntry:
        """Register a new entry in the catalog.

        Args:
            name: Unique entry name.
            entry: CatalogEntry with metadata.

        Returns:
            The registered CatalogEntry.

        Raises:
            ValueError: If entry already exists.
        """
        if name in self._entries:
            raise ValueError(f"Catalog entry '{name}' already exists. Use update().")

        entry.name = name
        entry.created_at = datetime.utcnow()
        entry.updated_at = datetime.utcnow()
        self._entries[name] = entry
        self._index_entry(name, entry)
        return entry

    def update(self, name: str, **kwargs: Any) -> Optional[CatalogEntry]:
        """Update an existing catalog entry.

        Args:
            name: Entry name.
            **kwargs: Fields to update.

        Returns:
            Updated CatalogEntry or None if not found.
        """
        entry = self._entries.get(name)
        if not entry:
            return None

        for key, value in kwargs.items():
            if hasattr(entry, key):
                setattr(entry, key, value)

        entry.updated_at = datetime.utcnow()
        self._index_entry(name, entry)
        return entry

    def deregister(self, name: str) -> bool:
        """Remove an entry from the catalog.

        Args:
            name: Entry name.

        Returns:
            True if removed.
        """
        if name not in self._entries:
            return False

        entry = self._entries.pop(name)
        self._remove_from_index(name, entry)
        return True

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[CatalogEntry]:
        """Get a catalog entry by name.

        Args:
            name: Entry name.

        Returns:
            CatalogEntry or None.
        """
        return self._entries.get(name)

    def list_all(
        self,
        entry_type: Optional[CatalogEntryType] = None,
        owner: Optional[str] = None,
        classification: Optional[DataClassification] = None,
        deprecated: Optional[bool] = None,
    ) -> List[CatalogEntry]:
        """List all catalog entries, optionally filtered.

        Args:
            entry_type: Filter by entry type.
            owner: Filter by owner.
            classification: Filter by classification.
            deprecated: Filter by deprecation status.

        Returns:
            List of matching CatalogEntry objects.
        """
        results = list(self._entries.values())

        if entry_type:
            results = [e for e in results if e.entry_type == entry_type]
        if owner:
            results = [e for e in results if e.owner == owner]
        if classification:
            results = [e for e in results if e.classification == classification]
        if deprecated is not None:
            results = [e for e in results if e.is_deprecated == deprecated]

        return results

    def get_by_type(self, entry_type: CatalogEntryType) -> List[CatalogEntry]:
        """Get all entries of a specific type."""
        return self.list_all(entry_type=entry_type)

    def get_by_owner(self, owner: str) -> List[CatalogEntry]:
        """Get all entries owned by a specific owner."""
        return self.list_all(owner=owner)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        entry_type: Optional[CatalogEntryType] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
    ) -> SearchResult:
        """Search the catalog for entries matching the query.

        Searches across: name, description, owner, tags, labels, column names.

        Args:
            query: Search query string.
            entry_type: Filter by entry type.
            tags: Filter by tags (AND logic).
            limit: Maximum results to return.

        Returns:
            SearchResult with matching entries.
        """
        query_lower = query.lower()
        results: List[CatalogEntry] = []

        for entry in self._entries.values():
            score = self._match_score(entry, query_lower)

            if score > 0:
                # Apply filters
                if entry_type and entry.entry_type != entry_type:
                    continue
                if tags and not all(t in entry.tags for t in tags):
                    continue

                results.append(entry)

        # Sort by match score (more matches = higher)
        results.sort(
            key=lambda e: self._match_score(e, query_lower),
            reverse=True,
        )

        return SearchResult(
            entries=results[:limit],
            total_matches=len(results),
            query=query,
            filters_applied={
                "entry_type": entry_type.value if entry_type else None,
                "tags": tags,
            },
        )

    def _match_score(self, entry: CatalogEntry, query: str) -> int:
        """Calculate match score for an entry against a query."""
        score = 0

        # Exact name match
        if query == entry.name.lower():
            score += 100
        elif query in entry.name.lower():
            score += 50

        # Description match
        if query in entry.description.lower():
            score += 30

        # Owner match
        if query in entry.owner.lower():
            score += 20

        # Tag match
        for tag in entry.tags:
            if query in tag.lower():
                score += 15

        # Label match
        for key, val in entry.labels.items():
            if query in key.lower() or query in val.lower():
                score += 10

        # Column name match
        for col in entry.columns:
            if query in col.name.lower():
                score += 10
            if query in col.description.lower():
                score += 5

        return score

    # ------------------------------------------------------------------
    # Index Management
    # ------------------------------------------------------------------

    def _index_entry(self, name: str, entry: CatalogEntry) -> None:
        """Index an entry for fast lookup."""
        # Index by type
        type_key = f"type:{entry.entry_type.value}"
        self._index.setdefault(type_key, set()).add(name)

        # Index by tag
        for tag in entry.tags:
            tag_key = f"tag:{tag.lower()}"
            self._index.setdefault(tag_key, set()).add(name)

        # Index by owner
        if entry.owner:
            owner_key = f"owner:{entry.owner.lower()}"
            self._index.setdefault(owner_key, set()).add(name)

        # Index by classification
        class_key = f"class:{entry.classification.value}"
        self._index.setdefault(class_key, set()).add(name)

    def _remove_from_index(self, name: str, entry: CatalogEntry) -> None:
        """Remove an entry from all indexes."""
        for key_set in self._index.values():
            key_set.discard(name)

    def get_by_tag(self, tag: str) -> List[CatalogEntry]:
        """Find entries by tag."""
        tag_key = f"tag:{tag.lower()}"
        names = self._index.get(tag_key, set())
        return [self._entries[n] for n in names if n in self._entries]

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_catalog_stats(self) -> Dict[str, Any]:
        """Get catalog-wide statistics."""
        type_counts: Dict[str, int] = {}
        owner_counts: Dict[str, int] = {}
        deprecated_count = 0

        for entry in self._entries.values():
            type_counts[entry.entry_type.value] = type_counts.get(entry.entry_type.value, 0) + 1
            if entry.owner:
                owner_counts[entry.owner] = owner_counts.get(entry.owner, 0) + 1
            if entry.is_deprecated:
                deprecated_count += 1

        return {
            "total_entries": len(self._entries),
            "by_type": type_counts,
            "by_owner": owner_counts,
            "deprecated": deprecated_count,
            "total_tags": len([k for k in self._index if k.startswith("tag:")]),
        }

    def get_entry_lineage_info(self, name: str) -> Dict[str, Any]:
        """Get lineage information for an entry."""
        entry = self._entries.get(name)
        if not entry:
            return {"error": f"Entry '{name}' not found"}

        upstream = [
            {"name": u, "exists": u in self._entries}
            for u in entry.lineage_upstream
        ]
        downstream = [
            {"name": d, "exists": d in self._entries}
            for d in entry.lineage_downstream
        ]

        return {
            "name": name,
            "upstream": upstream,
            "downstream": downstream,
            "upstream_count": len(entry.lineage_upstream),
            "downstream_count": len(entry.lineage_downstream),
        }
