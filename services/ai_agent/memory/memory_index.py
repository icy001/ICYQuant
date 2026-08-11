"""
Memory index for efficient cross-layer memory retrieval.

Provides unified indexing and search across all memory layers
with content-based and metadata-based filtering.

Responsibility: Cross-memory indexing and unified search.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── Index Types ──


class IndexEntryType(str, Enum):
    """Types of indexed entries across memory layers."""

    WORKING = "working"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"


@dataclass
class IndexEntry:
    """A lightweight index reference to a memory entry."""

    reference_id: str
    memory_layer: IndexEntryType
    original_key: str
    summary: str = ""
    tags: List[str] = field(default_factory=list)
    priority: float = 0.5
    created_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "reference_id": self.reference_id,
            "memory_layer": self.memory_layer.value,
            "original_key": self.original_key,
            "summary": self.summary[:100],
            "tags": self.tags,
            "priority": self.priority,
        }


# ── Memory Index ──


class MemoryIndex:
    """Unified index across all memory layers.

    Provides fast lookups and cross-layer search without
    needing to traverse each memory layer independently.

    Usage:
        index = MemoryIndex()
        index.add(IndexEntry(reference_id="1", memory_layer=IndexEntryType.WORKING, ...))
        results = index.search("market data")
    """

    def __init__(self) -> None:
        self._entries: Dict[str, IndexEntry] = {}
        self._tag_index: Dict[str, List[str]] = {}  # tag → reference_ids
        self._layer_index: Dict[str, List[str]] = {  # layer → reference_ids
            layer.value: [] for layer in IndexEntryType
        }
        logger.info("MemoryIndex created")

    # ── CRUD ──

    def add(self, entry: IndexEntry) -> None:
        """Add an entry to the index.

        Args:
            entry: The index entry to add.
        """
        self._entries[entry.reference_id] = entry
        self._layer_index[entry.memory_layer.value].append(entry.reference_id)

        for tag in entry.tags:
            self._tag_index.setdefault(tag, [])
            if entry.reference_id not in self._tag_index[tag]:
                self._tag_index[tag].append(entry.reference_id)

    def add_batch(self, entries: List[IndexEntry]) -> None:
        """Add multiple entries at once."""
        for entry in entries:
            self.add(entry)

    def remove(self, reference_id: str) -> bool:
        """Remove an entry from the index."""
        entry = self._entries.pop(reference_id, None)
        if not entry:
            return False

        self._layer_index[entry.memory_layer.value] = [
            rid for rid in self._layer_index[entry.memory_layer.value]
            if rid != reference_id
        ]
        for tag in entry.tags:
            if tag in self._tag_index:
                self._tag_index[tag] = [
                    rid for rid in self._tag_index[tag] if rid != reference_id
                ]

        return True

    def get(self, reference_id: str) -> Optional[IndexEntry]:
        """Get an index entry by reference ID."""
        return self._entries.get(reference_id)

    # ── Query ──

    def search(
        self,
        query: str,
        layers: Optional[List[IndexEntryType]] = None,
        limit: int = 20,
    ) -> List[IndexEntry]:
        """Search across indexed entries.

        Args:
            query: Search query string.
            layers: Optional filter by memory layers.
            limit: Maximum results.

        Returns:
            Matching index entries.
        """
        query_lower = query.lower()
        candidates = list(self._entries.values())

        if layers:
            layer_values = {l.value for l in layers}
            candidates = [e for e in candidates if e.memory_layer.value in layer_values]

        scored: List[tuple] = []
        for entry in candidates:
            score = 0
            if query_lower in entry.original_key.lower():
                score += 3
            if query_lower in entry.summary.lower():
                score += 2
            if any(query_lower in t.lower() for t in entry.tags):
                score += 1
            if score > 0:
                score += entry.priority  # Boost by priority
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    def search_by_tag(
        self,
        tag: str,
        layers: Optional[List[IndexEntryType]] = None,
    ) -> List[IndexEntry]:
        """Find entries by exact tag match."""
        reference_ids = self._tag_index.get(tag, [])
        entries = [self._entries[rid] for rid in reference_ids if rid in self._entries]

        if layers:
            layer_values = {l.value for l in layers}
            entries = [e for e in entries if e.memory_layer.value in layer_values]

        return entries

    def get_by_layer(self, layer: IndexEntryType) -> List[IndexEntry]:
        """Get all entries for a memory layer."""
        reference_ids = self._layer_index.get(layer.value, [])
        return [self._entries[rid] for rid in reference_ids if rid in self._entries]

    # ── Status ──

    @property
    def size(self) -> int:
        """Total indexed entries."""
        return len(self._entries)

    def get_summary(self) -> Dict[str, Any]:
        """Get index summary."""
        layer_counts = {
            layer: len(ids) for layer, ids in self._layer_index.items()
        }
        return {
            "total_entries": self.size,
            "by_layer": layer_counts,
            "unique_tags": len(self._tag_index),
        }

    def clear(self) -> None:
        """Clear all index entries."""
        self._entries.clear()
        self._tag_index.clear()
        for layer in self._layer_index:
            self._layer_index[layer].clear()
        logger.info("MemoryIndex cleared")
