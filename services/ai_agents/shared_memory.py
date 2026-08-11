"""
ICYQuant Shared Memory — centralized memory store for multi-agent collaboration.

Provides a thread-safe, namespace-isolated, in-memory KV store with
TTL-based expiry, versioning, pub/sub change notifications, and persistence
hooks for agent collaboration.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from .memory_bus import MemoryEntry

logger = logging.getLogger(__name__)


@dataclass
class NamespaceStats:
    entries: int = 0
    reads: int = 0
    writes: int = 0
    deletes: int = 0
    evictions: int = 0


class SharedMemory:
    """Centralized shared memory store for multi-agent collaboration.

    Features:
        - Namespace-isolated storage
        - TTL-based automatic entry expiry
        - Versioned entries for optimistic concurrency
        - Change notifications (pub/sub on key changes)
        - Periodic cleanup of expired entries
        - Memory usage tracking
    """

    def __init__(self, cleanup_interval_seconds: int = 60,
                 max_entries_per_namespace: int = 10000) -> None:
        # Core storage: namespace → key → value
        self._store: dict[str, dict[str, Any]] = {}
        self._cleanup_interval = cleanup_interval_seconds
        self._max_entries_per_ns = max_entries_per_namespace
        self._ns_stats: dict[str, NamespaceStats] = {}

        # Change subscribers: key_pattern → list of callbacks
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    # ── Lifecycle ──

    async def start(self) -> None:
        """Start the cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Shared memory cleanup started (interval=%ds)", self._cleanup_interval)

    async def stop(self) -> None:
        """Stop the cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Shared memory cleanup stopped")

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired entries."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._evict_expired()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Cleanup error: %s", exc)

    # ── CRUD Operations ──

    async def get(self, key: str, namespace: str = "default") -> Optional[Any]:
        """Get a raw value by key and namespace."""
        ns = self._store.get(namespace, {})
        entry = ns.get(key)
        self._ensure_stats(namespace).reads += 1
        return entry

    async def get_entry(self, key: str, namespace: str = "default") -> Optional[MemoryEntry]:
        """Get a full MemoryEntry by key and namespace."""
        val = await self.get(key, namespace)
        if isinstance(val, MemoryEntry):
            return val
        return None

    async def put(self, key: str, entry: MemoryEntry, namespace: str = "default") -> bool:
        """Store an entry, enforcing per-namespace limit."""
        async with self._lock:
            if namespace not in self._store:
                self._store[namespace] = {}

            ns = self._store[namespace]
            if len(ns) >= self._max_entries_per_ns and key not in ns:
                logger.warning("Namespace '%s' at capacity (%d)", namespace, self._max_entries_per_ns)
                return False

            is_update = key in ns
            ns[key] = entry
            self._ensure_stats(namespace).writes += 1

        # Notify subscribers
        await self._notify_change(key, namespace, is_update)
        return True

    async def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete an entry by key and namespace."""
        ns = self._store.get(namespace, {})
        if key in ns:
            del ns[key]
            self._ensure_stats(namespace).deletes += 1
            await self._notify_change(key, namespace, is_update=False, is_delete=True)
            return True
        return False

    async def exists(self, key: str, namespace: str = "default") -> bool:
        return key in self._store.get(namespace, {})

    # ── Batch Operations ──

    async def get_many(self, keys: list[str],
                       namespace: str = "default") -> dict[str, Any]:
        """Get multiple entries by key list."""
        ns = self._store.get(namespace, {})
        results = {}
        for key in keys:
            if key in ns:
                val = ns[key]
                results[key] = val.value if isinstance(val, MemoryEntry) else val
        self._ensure_stats(namespace).reads += len(keys)
        return results

    async def put_many(self, entries: dict[str, MemoryEntry],
                       namespace: str = "default") -> int:
        """Store multiple entries atomically. Returns count stored."""
        async with self._lock:
            if namespace not in self._store:
                self._store[namespace] = {}

            ns = self._store[namespace]
            stored = 0
            for key, entry in entries.items():
                if len(ns) < self._max_entries_per_ns or key in ns:
                    ns[key] = entry
                    stored += 1
            self._ensure_stats(namespace).writes += stored

        for key in entries:
            await self._notify_change(key, namespace, key in ns)
        return stored

    # ── Query ──

    async def list_keys(self, namespace: str = "default") -> list[str]:
        """List all keys in a namespace."""
        return list(self._store.get(namespace, {}).keys())

    async def count(self, namespace: str = "default") -> int:
        """Count entries in a namespace."""
        return len(self._store.get(namespace, {}))

    async def total_entries(self) -> int:
        """Count entries across all namespaces."""
        return sum(len(ns) for ns in self._store.values())

    # ── Expiry ──

    async def _evict_expired(self) -> int:
        """Evict expired entries. Returns number evicted."""
        evicted = 0
        for namespace in list(self._store.keys()):
            ns = self._store.get(namespace, {})
            expired_keys = []
            for key, val in ns.items():
                if isinstance(val, MemoryEntry) and val.is_expired():
                    expired_keys.append(key)

            for key in expired_keys:
                del ns[key]
                evicted += 1
                self._ensure_stats(namespace).evictions += 1

        if evicted > 0:
            logger.debug("Evicted %d expired entries", evicted)
        return evicted

    # ── Change Notifications ──

    def subscribe(self, namespace: str, queue: asyncio.Queue) -> None:
        """Subscribe to changes in a namespace."""
        key = f"ns:{namespace}"
        if key not in self._subscribers:
            self._subscribers[key] = []
        self._subscribers[key].append(queue)

    def unsubscribe(self, namespace: str, queue: asyncio.Queue) -> None:
        """Remove a subscription."""
        key = f"ns:{namespace}"
        if key in self._subscribers:
            self._subscribers[key] = [q for q in self._subscribers[key] if q is not queue]

    async def _notify_change(self, key: str, namespace: str,
                             is_update: bool, is_delete: bool = False) -> None:
        """Notify subscribers of a change."""
        subscribers = self._subscribers.get(f"ns:{namespace}", [])
        if not subscribers:
            return

        event = {
            "key": key,
            "namespace": namespace,
            "action": "delete" if is_delete else ("update" if is_update else "create"),
        }

        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.debug("Subscriber queue full for %s/%s", namespace, key)

    # ── Stats ──

    def _ensure_stats(self, namespace: str) -> NamespaceStats:
        if namespace not in self._ns_stats:
            self._ns_stats[namespace] = NamespaceStats()
        ns_data = self._store.get(namespace, {})
        self._ns_stats[namespace].entries = len(ns_data)
        return self._ns_stats[namespace]

    def get_stats(self, namespace: str) -> Optional[NamespaceStats]:
        stats = self._ns_stats.get(namespace)
        if stats:
            ns_data = self._store.get(namespace, {})
            stats.entries = len(ns_data)
        return stats

    @property
    def namespaces(self) -> list[str]:
        return list(self._store.keys())

    @property
    def total_size(self) -> int:
        return sum(len(ns) for ns in self._store.values())
