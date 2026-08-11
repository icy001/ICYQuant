"""
Short-term memory for current session caching.

Provides temporary storage scoped to a single session lifetime.
Used for caching recent context, intermediate results, and conversation turns.

Responsibility: Current session cache with automatic eviction.
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ShortTermEntry:
    """An entry in short-term memory."""

    entry_id: str = field(default_factory=lambda: uuid4().hex)
    key: str = ""
    value: Any = None
    session_id: str = ""
    created_at: float = field(default_factory=time.monotonic)
    ttl_seconds: float = 600.0  # 10 minutes default
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if entry has exceeded TTL."""
        return (time.monotonic() - self.created_at) > self.ttl_seconds


class ShortTermMemory:
    """Short-term memory with TTL-based eviction.

    Scoped to a session lifetime, providing fast access to
    recently used context and intermediate results.

    Uses LRU-style eviction when capacity is reached.

    Usage:
        stm = ShortTermMemory(capacity=100, default_ttl=600)
        stm.put("analysis_result", result, session_id="sess_1")
        value = stm.get("analysis_result")
    """

    def __init__(self, capacity: int = 1000, default_ttl: float = 600.0) -> None:
        self.capacity = capacity
        self.default_ttl = default_ttl
        self._entries: OrderedDict[str, ShortTermEntry] = OrderedDict()
        self._stats: Dict[str, int] = {"puts": 0, "gets": 0, "hits": 0, "misses": 0, "evictions": 0}
        logger.info("ShortTermMemory created")

    # ── CRUD ──

    def put(
        self,
        key: str,
        value: Any,
        session_id: str = "",
        ttl_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store a value in short-term memory.

        Args:
            key: Storage key.
            value: Value to store.
            session_id: Associated session.
            ttl_seconds: Time-to-live override.
            metadata: Additional metadata.
        """
        self._evict_expired()

        # Enforce capacity via LRU eviction
        if len(self._entries) >= self.capacity:
            oldest = next(iter(self._entries))
            del self._entries[oldest]
            self._stats["evictions"] += 1

        entry = ShortTermEntry(
            key=key,
            value=value,
            session_id=session_id,
            ttl_seconds=ttl_seconds or self.default_ttl,
            metadata=metadata or {},
        )

        # Move to end if re-inserting (LRU)
        if key in self._entries:
            del self._entries[key]
        self._entries[key] = entry
        self._stats["puts"] += 1

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from short-term memory.

        Args:
            key: Storage key.

        Returns:
            Stored value or None if not found/expired.
        """
        entry = self._entries.get(key)
        self._stats["gets"] += 1

        if entry is None:
            self._stats["misses"] += 1
            return None

        if entry.is_expired:
            del self._entries[key]
            self._stats["misses"] += 1
            return None

        entry.access_count += 1
        # Move to end (LRU)
        self._entries.move_to_end(key)
        self._stats["hits"] += 1
        return entry.value

    def has(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        entry = self._entries.get(key)
        if entry and not entry.is_expired:
            return True
        return False

    def delete(self, key: str) -> bool:
        """Remove a key from short-term memory."""
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    # ── Session Operations ──

    def get_by_session(self, session_id: str) -> Dict[str, Any]:
        """Get all entries for a session."""
        result = {}
        for key, entry in self._entries.items():
            if entry.session_id == session_id and not entry.is_expired:
                result[key] = entry.value
        return result

    def clear_session(self, session_id: str) -> int:
        """Remove all entries for a session.

        Returns:
            Number of entries removed.
        """
        to_remove = [
            key for key, entry in self._entries.items()
            if entry.session_id == session_id
        ]
        for key in to_remove:
            del self._entries[key]
        logger.debug(f"Cleared {len(to_remove)} entries for session: {session_id}")
        return len(to_remove)

    # ── Maintenance ──

    def _evict_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries evicted.
        """
        expired = [
            key for key, entry in self._entries.items()
            if entry.is_expired
        ]
        for key in expired:
            del self._entries[key]
        return len(expired)

    def clear(self) -> None:
        """Clear all short-term memory."""
        self._entries.clear()

    # ── Status ──

    @property
    def size(self) -> int:
        """Current number of entries."""
        return len(self._entries)

    def get_summary(self) -> Dict[str, Any]:
        """Get short-term memory summary."""
        return {
            "size": self.size,
            "capacity": self.capacity,
            "stats": self._stats,
            "hit_rate": (
                self._stats["hits"] / max(self._stats["gets"], 1)
            ),
        }
