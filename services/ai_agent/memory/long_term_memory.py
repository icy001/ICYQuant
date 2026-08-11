"""
Long-term memory for persistent knowledge and experience.

Stores accumulated knowledge, learned patterns, and historical
insights that persist across sessions.

Responsibility: Long-term knowledge retention and retrieval.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── Memory Types ──


class MemoryCategory(str, Enum):
    """Categories of long-term memories."""

    KNOWLEDGE = "knowledge"         # Factual knowledge
    SKILL = "skill"                 # Learned procedures
    PATTERN = "pattern"             # Recognized patterns
    PREFERENCE = "preference"       # User preferences
    INSIGHT = "insight"             # Derived insights
    RELATIONSHIP = "relationship"   # Entity relationships
    CUSTOM = "custom"               # Custom category


class MemoryPriority(str, Enum):
    """Retrieval priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class LongTermEntry:
    """A long-term memory entry."""

    entry_id: str = field(default_factory=lambda: uuid4().hex)
    key: str = ""
    value: Any = None
    category: MemoryCategory = MemoryCategory.KNOWLEDGE
    priority: MemoryPriority = MemoryPriority.MEDIUM
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed_at: Optional[datetime] = None
    access_count: int = 0
    relevance_score: float = 0.5
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""

    def touch(self) -> None:
        """Record an access."""
        self.last_accessed_at = datetime.now(timezone.utc)
        self.access_count += 1


class LongTermMemory:
    """Long-term memory for persistent knowledge.

    Stores accumulated knowledge that persists across sessions.
    Uses an in-memory store; in production this delegates to a vector DB
    or knowledge graph.

    Usage:
        ltm = LongTermMemory()
        ltm.store("market_opening_hours", {"NYSE": "9:30-16:00"}, category=MemoryCategory.KNOWLEDGE)
        result = ltm.retrieve("market_opening_hours")
    """

    def __init__(self) -> None:
        self._store: Dict[str, LongTermEntry] = {}
        self._index: Dict[str, List[str]] = {}  # tag → entry_ids
        logger.info("LongTermMemory created")

    # ── CRUD ──

    def store(
        self,
        key: str,
        value: Any,
        category: MemoryCategory = MemoryCategory.KNOWLEDGE,
        priority: MemoryPriority = MemoryPriority.MEDIUM,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "",
    ) -> LongTermEntry:
        """Store a memory entry.

        Args:
            key: Unique memory key.
            value: The knowledge/insight to store.
            category: Memory category.
            priority: Retrieval priority.
            tags: Indexing tags.
            metadata: Additional metadata.
            source: Origin of this knowledge.

        Returns:
            The stored entry.
        """
        entry = LongTermEntry(
            key=key,
            value=value,
            category=category,
            priority=priority,
            tags=tags or [],
            metadata=metadata or {},
            source=source,
        )
        self._store[key] = entry

        # Update tag index
        for tag in entry.tags:
            if tag not in self._index:
                self._index[tag] = []
            if key not in self._index[tag]:
                self._index[tag].append(key)

        logger.debug(f"LTM stored: {key} [{category.value}]")
        return entry

    def retrieve(self, key: str) -> Optional[LongTermEntry]:
        """Retrieve a memory entry by key.

        Args:
            key: Memory key.

        Returns:
            The stored entry or None.
        """
        entry = self._store.get(key)
        if entry:
            entry.touch()
        return entry

    def update(self, key: str, value: Any) -> bool:
        """Update an existing memory entry."""
        entry = self._store.get(key)
        if not entry:
            return False
        entry.value = value
        entry.updated_at = datetime.now(timezone.utc)
        return True

    def delete(self, key: str) -> bool:
        """Remove a memory entry."""
        entry = self._store.pop(key, None)
        if entry:
            for tag in entry.tags:
                if tag in self._index and key in self._index[tag]:
                    self._index[tag].remove(key)
            return True
        return False

    # ── Query ──

    def find_by_category(self, category: MemoryCategory) -> List[LongTermEntry]:
        """Find entries by category."""
        return [e for e in self._store.values() if e.category == category]

    def find_by_tag(self, tag: str) -> List[LongTermEntry]:
        """Find entries by tag."""
        keys = self._index.get(tag, [])
        return [self._store[k] for k in keys if k in self._store]

    def find_by_priority(self, priority: MemoryPriority) -> List[LongTermEntry]:
        """Find entries by priority level."""
        return [e for e in self._store.values() if e.priority == priority]

    def search(self, query: str, limit: int = 10) -> List[LongTermEntry]:
        """Simple keyword search across keys and tags.

        Args:
            query: Search query string.
            limit: Maximum results.

        Returns:
            Matching entries.
        """
        query_lower = query.lower()
        results = []
        for entry in self._store.values():
            if query_lower in entry.key.lower():
                results.append(entry)
            elif any(query_lower in t.lower() for t in entry.tags):
                results.append(entry)
        return sorted(results, key=lambda e: e.relevance_score, reverse=True)[:limit]

    def get_all(self) -> List[LongTermEntry]:
        """Get all stored entries."""
        return list(self._store.values())

    # ── Status ──

    @property
    def size(self) -> int:
        """Total stored entries."""
        return len(self._store)

    def get_summary(self) -> Dict[str, Any]:
        """Get long-term memory summary."""
        category_counts: Dict[str, int] = {}
        for entry in self._store.values():
            cat = entry.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "size": self.size,
            "by_category": category_counts,
            "indexed_tags": len(self._index),
            "total_accesses": sum(e.access_count for e in self._store.values()),
        }
