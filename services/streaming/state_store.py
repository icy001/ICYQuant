"""
State Store — key-value state storage for stateful stream processing
with transactional support and checkpoint integration.

Commit 16 Part 1.4
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class StateValue:
    """A state entry with metadata."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.monotonic)
    updated_at: float = field(default_factory=time.monotonic)
    version: int = 0
    ttl_ms: Optional[int] = None  # Time-to-live in ms


class StateTransaction:
    """An atomic transaction for state operations."""

    def __init__(self, store: StateStore) -> None:
        self._store = store
        self._pending: dict[str, Optional[StateValue]] = {}
        self._committed = False

    async def put(self, key: str, value: Any, ttl_ms: Optional[int] = None) -> None:
        """Stage a put operation."""
        now = time.monotonic()
        sv = StateValue(key=key, value=value, updated_at=now, ttl_ms=ttl_ms)
        self._pending[key] = sv

    async def delete(self, key: str) -> None:
        """Stage a delete operation."""
        self._pending[key] = None

    async def commit(self) -> None:
        """Commit all staged operations."""
        for key, value in self._pending.items():
            if value is None:
                await self._store.delete(key)
            else:
                await self._store.put(key, value.value, ttl_ms=value.ttl_ms)
        self._committed = True

    async def rollback(self) -> None:
        """Discard all staged operations."""
        self._pending.clear()


class StateStore:
    """
    Key-value state storage for stateful stream processing.

    Provides atomic get/put/delete with TTL support, transactional
    batch operations, and snapshot/restore for checkpointing.

    Usage::

        store = StateStore()
        await store.put("vwap_BTC", {"volume": 1000, "cum_pv": 50000000})
        state = await store.get("vwap_BTC")
        snapshot = await store.snapshot()
        await store.restore(snapshot)
    """

    def __init__(self, max_size: int = 1000000) -> None:
        self.max_size = max_size
        self._store: dict[str, StateValue] = {}
        self._lock = asyncio.Lock()
        self._puts = 0
        self._gets = 0
        self._deletes = 0

    async def get(self, key: str) -> Optional[Any]:
        """Get a value by key."""
        self._gets += 1
        sv = self._store.get(key)
        if sv is None:
            return None

        # Check TTL
        if sv.ttl_ms is not None:
            elapsed = (time.monotonic() - sv.created_at) * 1000
            if elapsed > sv.ttl_ms:
                await self.delete(key)
                return None

        return sv.value

    async def put(self, key: str, value: Any, ttl_ms: Optional[int] = None) -> None:
        """Put a value with optional TTL."""
        async with self._lock:
            if key in self._store:
                sv = self._store[key]
                sv.value = value
                sv.updated_at = time.monotonic()
                sv.version += 1
                sv.ttl_ms = ttl_ms
            else:
                if len(self._store) >= self.max_size:
                    raise RuntimeError(f"StateStore at max capacity ({self.max_size})")
                self._store[key] = StateValue(
                    key=key, value=value, ttl_ms=ttl_ms,
                )
            self._puts += 1

    async def delete(self, key: str) -> bool:
        """Delete a key."""
        async with self._lock:
            if key in self._store:
                del self._store[key]
                self._deletes += 1
                return True
        return False

    async def contains(self, key: str) -> bool:
        """Check if a key exists."""
        return key in self._store

    async def keys(self) -> list[str]:
        """Get all keys."""
        return list(self._store.keys())

    async def size(self) -> int:
        """Get the number of entries."""
        return len(self._store)

    async def clear(self) -> None:
        """Clear all state."""
        async with self._lock:
            count = len(self._store)
            self._store.clear()
            logger.info("StateStore cleared (%d entries).", count)

    async def begin_transaction(self) -> StateTransaction:
        """Begin a new transaction."""
        return StateTransaction(self)

    async def snapshot(self) -> dict[str, Any]:
        """Take a snapshot of all state for checkpointing."""
        return {
            key: sv.value
            for key, sv in self._store.items()
        }

    async def restore(self, snapshot: dict[str, Any]) -> None:
        """Restore state from a snapshot."""
        async with self._lock:
            self._store.clear()
            for key, value in snapshot.items():
                self._store[key] = StateValue(key=key, value=value)

    async def stats(self) -> dict[str, Any]:
        """Get state store statistics."""
        return {
            "size": len(self._store),
            "max_size": self.max_size,
            "puts": self._puts,
            "gets": self._gets,
            "deletes": self._deletes,
            "utilization": len(self._store) / self.max_size,
        }
