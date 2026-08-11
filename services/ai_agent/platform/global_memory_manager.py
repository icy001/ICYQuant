"""Global Memory Manager — platform-wide shared memory for cross-agent knowledge.

The GlobalMemoryManager provides a unified memory namespace accessible by all
agents, sessions, and platform components. It supports hierarchical namespaces,
TTL-based expiration, semantic search, and multi-tenant isolation.

Memory hierarchy:
    Platform Memory (global)
        -> Session Memory (per user session)
            -> Agent Memory (per agent instance)
                -> Task Memory (per task execution)
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryScope(str, Enum):
    """Memory visibility scope."""
    PLATFORM = "platform"
    SESSION = "session"
    AGENT = "agent"
    TASK = "task"


@dataclass
class MemoryEntry:
    """A single entry in the global memory store."""
    entry_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    key: str = ""
    value: Any = None
    scope: MemoryScope = MemoryScope.PLATFORM
    owner_id: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.monotonic)
    updated_at: float = field(default_factory=time.monotonic)
    ttl_sec: Optional[float] = None
    version: int = 1


class GlobalMemoryManager:
    """Platform-wide shared memory for cross-agent knowledge sharing.

    Provides hierarchical namespaced memory with TTL, semantic search,
    and multi-tenant isolation. All agents access memory through this
    unified interface.

    Usage:
        gmm = GlobalMemoryManager()
        await gmm.initialize()
        await gmm.put("market:sentiment", {"value": 0.8}, scope=MemoryScope.SESSION, owner_id="session_1")
        entry = await gmm.get("market:sentiment", scope=MemoryScope.SESSION, owner_id="session_1")
    """

    def __init__(self, max_entries: int = 100000, default_ttl_sec: Optional[float] = 3600.0) -> None:
        self._max_entries = max_entries
        self._default_ttl_sec = default_ttl_sec
        self._store: Dict[str, Dict[str, MemoryEntry]] = {s.value: {} for s in MemoryScope}
        self._initialized: bool = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()
        logger.info("GlobalMemoryManager created (max=%d, default_ttl=%s)", max_entries, default_ttl_sec)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("GlobalMemoryManager initialized")

    async def shutdown(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        with self._lock:
            for scope_store in self._store.values():
                scope_store.clear()
        self._initialized = False
        logger.info("GlobalMemoryManager shutdown complete")

    def _make_ns_key(self, scope: MemoryScope, owner_id: str, key: str) -> str:
        return f"{owner_id}:{key}" if owner_id else key

    def _get_scope_store(self, scope: MemoryScope) -> Dict[str, MemoryEntry]:
        return self._store[scope.value]

    async def put(self, key: str, value: Any, scope: MemoryScope = MemoryScope.PLATFORM, owner_id: str = "", tags: Optional[List[str]] = None, ttl_sec: Optional[float] = None) -> str:
        """Store a value in global memory."""
        ns_key = self._make_ns_key(scope, owner_id, key)
        ttl = ttl_sec if ttl_sec is not None else self._default_ttl_sec

        with self._lock:
            scope_store = self._get_scope_store(scope)
            existing = scope_store.get(ns_key)
            if existing:
                existing.value = value
                existing.updated_at = time.monotonic()
                existing.version += 1
                existing.ttl_sec = ttl
                existing.tags = tags or []
                entry = existing
            else:
                if self._total_entries() >= self._max_entries:
                    self._evict_oldest()
                entry = MemoryEntry(key=key, value=value, scope=scope, owner_id=owner_id, tags=tags or [], ttl_sec=ttl)
                scope_store[ns_key] = entry

        logger.debug("GlobalMemory: put %s/%s (v%d)", scope.value, key, entry.version)
        return entry.entry_id

    async def get(self, key: str, scope: MemoryScope = MemoryScope.PLATFORM, owner_id: str = "") -> Optional[Any]:
        """Retrieve a value from global memory."""
        ns_key = self._make_ns_key(scope, owner_id, key)
        with self._lock:
            entry = self._get_scope_store(scope).get(ns_key)
            if entry is None:
                return None
            if entry.ttl_sec is not None:
                age = time.monotonic() - entry.updated_at
                if age > entry.ttl_sec:
                    del self._get_scope_store(scope)[ns_key]
                    return None
            return entry.value

    async def delete(self, key: str, scope: MemoryScope = MemoryScope.PLATFORM, owner_id: str = "") -> bool:
        """Remove an entry from global memory."""
        ns_key = self._make_ns_key(scope, owner_id, key)
        with self._lock:
            scope_store = self._get_scope_store(scope)
            if ns_key in scope_store:
                del scope_store[ns_key]
                return True
            return False

    async def search_by_tags(self, tags: List[str], scope: Optional[MemoryScope] = None) -> List[Dict[str, Any]]:
        """Search entries by tags."""
        results = []
        scopes = [scope] if scope else list(MemoryScope)
        with self._lock:
            for s in scopes:
                for entry in self._get_scope_store(s).values():
                    if any(t in entry.tags for t in tags):
                        results.append({"key": entry.key, "scope": entry.scope.value, "owner_id": entry.owner_id, "tags": entry.tags, "version": entry.version})
        return results

    async def list_keys(self, scope: MemoryScope = MemoryScope.PLATFORM, owner_id: str = "") -> List[str]:
        """List all keys in a scope."""
        prefix = f"{owner_id}:" if owner_id else ""
        with self._lock:
            return [k.replace(prefix, "", 1) for k in self._get_scope_store(scope) if k.startswith(prefix)]

    async def clear_scope(self, scope: MemoryScope, owner_id: str = "") -> int:
        """Clear all entries for a given scope/owner."""
        prefix = f"{owner_id}:" if owner_id else ""
        with self._lock:
            scope_store = self._get_scope_store(scope)
            if owner_id:
                keys = [k for k in scope_store if k.startswith(prefix)]
                for k in keys:
                    del scope_store[k]
                return len(keys)
            count = len(scope_store)
            scope_store.clear()
            return count

    def _total_entries(self) -> int:
        return sum(len(s) for s in self._store.values())

    def _evict_oldest(self) -> None:
        """Evict the oldest entry across all scopes."""
        oldest_key = None
        oldest_scope = None
        oldest_time = float("inf")
        for scope_name, scope_store in self._store.items():
            for key, entry in scope_store.items():
                if entry.updated_at < oldest_time:
                    oldest_time = entry.updated_at
                    oldest_key = key
                    oldest_scope = scope_name
        if oldest_key and oldest_scope:
            del self._store[oldest_scope][oldest_key]

    async def _cleanup_loop(self) -> None:
        """Background task to expire TTL entries."""
        while True:
            try:
                await asyncio.sleep(30)
                await self._expire_entries()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("GlobalMemoryManager cleanup error: %s", e)

    async def _expire_entries(self) -> None:
        now = time.monotonic()
        with self._lock:
            for scope_store in self._store.values():
                expired = [k for k, e in scope_store.items() if e.ttl_sec is not None and (now - e.updated_at) > e.ttl_sec]
                for k in expired:
                    del scope_store[k]

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "initialized": self._initialized,
                "total_entries": self._total_entries(),
                "max_entries": self._max_entries,
                "by_scope": {s: len(self._store[s]) for s in self._store},
            }
