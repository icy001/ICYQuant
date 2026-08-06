"""Dataset Catalog — structured directory of available research datasets.

The catalog maintains metadata about all registered datasets including
ownership, schema, tags, and version information for fast discovery.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CatalogEntry:
    """A single entry in the dataset catalog."""

    def __init__(
        self,
        dataset_id: str,
        name: str,
        source: str = "",
        schema: Optional[Dict[str, Any]] = None,
        owner: Optional[str] = None,
        tags: Optional[List[str]] = None,
        description: str = "",
        created_at: Optional[datetime] = None,
    ) -> None:
        self.dataset_id = dataset_id
        self.name = name
        self.source = source
        self.schema = schema or {}
        self.owner = owner
        self.tags = tags or []
        self.description = description
        self.created_at = created_at or datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "name": self.name,
            "source": self.source,
            "schema": self.schema,
            "owner": self.owner,
            "tags": self.tags,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
        }


class DatasetCatalog:
    """Structured directory of research datasets.

    Maintains:
    * Dataset metadata (name, source, owner)
    * Schema information
    * Tag-based organization
    * Search capabilities

    Architecture::

        Dataset → Owner → Schema → Tags → Version
    """

    def __init__(self) -> None:
        self._entries: Dict[str, CatalogEntry] = {}

    # ── entry management ──────────────────────────────────────────────────

    def add_entry(
        self,
        dataset_id: str,
        name: str,
        source: str = "",
        schema: Optional[Dict[str, Any]] = None,
        owner: Optional[str] = None,
        tags: Optional[List[str]] = None,
        description: str = "",
    ) -> CatalogEntry:
        """Add or update a catalog entry."""
        entry = CatalogEntry(
            dataset_id=dataset_id,
            name=name,
            source=source,
            schema=schema,
            owner=owner,
            tags=tags,
            description=description,
        )
        self._entries[dataset_id] = entry
        logger.debug("Catalog entry added: %s", dataset_id)
        return entry

    def get_entry(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        entry = self._entries.get(dataset_id)
        return entry.to_dict() if entry else None

    def remove_entry(self, dataset_id: str) -> bool:
        if dataset_id in self._entries:
            del self._entries[dataset_id]
            return True
        return False

    def list_all(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._entries.values()]

    # ── search ────────────────────────────────────────────────────────────

    def search(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
        owner: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search catalog entries with multiple filter criteria."""
        results = list(self._entries.values())

        if query:
            q = query.lower()
            results = [
                e for e in results
                if q in e.name.lower() or q in e.description.lower()
            ]

        if source:
            results = [e for e in results if e.source == source]

        if owner:
            results = [e for e in results if e.owner == owner]

        if tags:
            results = [
                e for e in results
                if any(t in e.tags for t in tags)
            ]

        return [e.to_dict() for e in results]

    def list_by_source(self, source: str) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._entries.values() if e.source == source]

    def list_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._entries.values() if tag in e.tags]

    def list_by_owner(self, owner: str) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._entries.values() if e.owner == owner]

    # ── stats ─────────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self._entries)

    def summary(self) -> Dict[str, Any]:
        sources: Dict[str, int] = {}
        for e in self._entries.values():
            sources[e.source] = sources.get(e.source, 0) + 1
        return {
            "total": self.count,
            "by_source": sources,
        }

    def __repr__(self) -> str:
        return f"DatasetCatalog(entries={self.count})"
