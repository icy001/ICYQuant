"""
ICYQuant Research Memory — persistent context storage for research sessions.

Stores prompts, context, intermediate results, final reports, and
makes them reusable across research tasks for continuity and learning.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    PROMPT = "prompt"
    CONTEXT = "context"
    INTERMEDIATE = "intermediate"
    REPORT = "report"
    CITATION = "citation"
    EVIDENCE = "evidence"


@dataclass
class MemoryEntry:
    """A single entry in the research memory."""
    entry_id: str
    memory_type: MemoryType
    content: Any
    session_id: str = ""
    user_id: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    access_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class ResearchMemory:
    """Hierarchical memory system for research context persistence.

    Organizes memory into:
        - Short-term: Current session working memory
        - Long-term: Cross-session reusable knowledge
        - Episodic: Past research task traces

    Supports:
        - Prompt → Context → Intermediate Result → Final Report chain
        - Cross-research-task reuse via semantic recall
        - Tag-based organization
        - LRU eviction for capacity management
    """

    def __init__(self, max_entries: int = 10000) -> None:
        self._max_entries = max_entries
        self._entries: OrderedDict[str, MemoryEntry] = OrderedDict()
        self._tag_index: dict[str, set[str]] = {}

    def store(
        self,
        entry_id: str,
        memory_type: MemoryType,
        content: Any,
        session_id: str = "",
        user_id: str = "",
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Store an entry in research memory."""
        if len(self._entries) >= self._max_entries:
            self._evict_lru()

        entry = MemoryEntry(
            entry_id=entry_id,
            memory_type=memory_type,
            content=content,
            session_id=session_id,
            user_id=user_id,
            tags=tags or [],
            metadata=metadata or {},
        )

        self._entries[entry_id] = entry
        self._entries.move_to_end(entry_id)

        # Update tag index
        for tag in entry.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(entry_id)

        return entry_id

    def recall(self, entry_id: str) -> Optional[MemoryEntry]:
        """Recall an entry by ID."""
        entry = self._entries.get(entry_id)
        if entry:
            entry.access_count += 1
            self._entries.move_to_end(entry_id)
        return entry

    def search_by_tags(self, tags: list[str]) -> list[MemoryEntry]:
        """Find entries matching any of the given tags."""
        matching_ids: set[str] = set()
        for tag in tags:
            matching_ids.update(self._tag_index.get(tag, set()))

        return [self._entries[eid] for eid in matching_ids if eid in self._entries]

    def search_by_type(self, memory_type: MemoryType, limit: int = 100) -> list[MemoryEntry]:
        """Find entries of a specific type."""
        results = [e for e in self._entries.values() if e.memory_type == memory_type]
        return results[-limit:]

    def get_session_memory(self, session_id: str) -> list[MemoryEntry]:
        """Get all entries for a specific session."""
        return [e for e in self._entries.values() if e.session_id == session_id]

    def delete(self, entry_id: str) -> bool:
        """Delete an entry from memory."""
        entry = self._entries.pop(entry_id, None)
        if entry:
            for tag in entry.tags:
                if tag in self._tag_index:
                    self._tag_index[tag].discard(entry_id)
            return True
        return False

    def clear_session(self, session_id: str) -> int:
        """Clear all entries for a session."""
        entries = self.get_session_memory(session_id)
        for e in entries:
            self.delete(e.entry_id)
        return len(entries)

    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if self._entries:
            oldest_id = next(iter(self._entries))
            self.delete(oldest_id)
            logger.debug("Evicted LRU memory entry %s", oldest_id)

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def tag_count(self) -> int:
        return len(self._tag_index)
