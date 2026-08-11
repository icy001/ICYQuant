"""
Working memory for current task context.

Provides immediate, mutable state for the active agent task.
Scoped to current execution - cleared on task completion.

Responsibility: Current task context and intermediate state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class WorkingMemoryEntry:
    """A single entry in working memory."""

    entry_id: str = field(default_factory=lambda: uuid4().hex)
    key: str = ""
    value: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: Optional[float] = None
    entry_type: str = "generic"
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkingMemory:
    """Current task working memory.

    Holds immediate task context, intermediate computation results,
    and temporary state for the active agent execution.

    Lifecycle: Created at task start, cleared at task completion.

    Usage:
        wm = WorkingMemory()
        wm.set("current_price", 50000.0)
        value = wm.get("current_price")
        wm.clear()
    """

    def __init__(self, max_entries: int = 1000) -> None:
        self.max_entries = max_entries
        self._entries: Dict[str, Any] = {}
        self._task_id: str = ""
        self._stats: Dict[str, Any] = {
            "sets": 0,
            "gets": 0,
            "deletes": 0,
            "hits": 0,
            "misses": 0,
        }
        logger.debug("WorkingMemory created")

    # ── CRUD ──

    def set(self, key: str, value: Any) -> None:
        """Store a value in working memory.

        Args:
            key: Storage key.
            value: Any serializable value.
        """
        self._entries[key] = value
        self._stats["sets"] += 1

        # Enforce max entries
        if len(self._entries) > self.max_entries:
            oldest = next(iter(self._entries))
            del self._entries[oldest]

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from working memory.

        Args:
            key: Storage key.
            default: Default value if key not found.

        Returns:
            Stored value or default.
        """
        if key in self._entries:
            self._stats["hits"] += 1
            self._stats["gets"] += 1
            return self._entries[key]
        self._stats["misses"] += 1
        self._stats["gets"] += 1
        return default

    def has(self, key: str) -> bool:
        """Check if key exists in working memory."""
        return key in self._entries

    def delete(self, key: str) -> bool:
        """Remove a key from working memory.

        Returns:
            True if key was removed.
        """
        if key in self._entries:
            del self._entries[key]
            self._stats["deletes"] += 1
            return True
        return False

    def update(self, data: Dict[str, Any]) -> None:
        """Batch update multiple keys."""
        for key, value in data.items():
            self.set(key, value)

    # ── Batch Operations ──

    def get_all(self) -> Dict[str, Any]:
        """Get all entries in working memory."""
        return dict(self._entries)

    def keys(self) -> List[str]:
        """Get all keys in working memory."""
        return list(self._entries.keys())

    # ── Lifecycle ──

    def bind_task(self, task_id: str) -> None:
        """Bind working memory to a task."""
        self._task_id = task_id
        logger.debug(f"WorkingMemory bound to task: {task_id}")

    def clear(self) -> None:
        """Clear all working memory entries."""
        self._entries.clear()
        self._task_id = ""
        self._stats = {"sets": 0, "gets": 0, "deletes": 0, "hits": 0, "misses": 0}
        logger.debug("WorkingMemory cleared")

    # ── Status ──

    @property
    def size(self) -> int:
        """Number of entries in working memory."""
        return len(self._entries)

    def get_stats(self) -> Dict[str, Any]:
        """Get working memory statistics."""
        return {
            **self._stats,
            "size": self.size,
            "max_entries": self.max_entries,
            "task_id": self._task_id,
        }
