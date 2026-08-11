"""
ICYQuant Memory Bus — agent access layer to shared memory.

Provides a controlled interface for agents to read/write shared memory
with access policies, versioning, TTL, and namespace isolation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AccessLevel(str, Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    NONE = "none"


@dataclass
class MemoryEntry:
    """A single entry in shared memory with metadata."""
    key: str
    value: Any
    namespace: str = "default"
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    ttl_seconds: int = 0  # 0 = no expiry
    access_level: AccessLevel = AccessLevel.READ
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        if self.ttl_seconds <= 0:
            return False
        elapsed = (datetime.now(timezone.utc) - self.updated_at).total_seconds()
        return elapsed > self.ttl_seconds


class MemoryBus:
    """Controlled access layer for agents to shared memory.

    Features:
        - Namespace isolation for different agent types
        - Access control (read/write/admin per namespace per agent)
        - TTL-based entry expiration
        - Version tracking for optimistic concurrency
        - Entry tagging for query capability
        - Multi-key atomic batch operations
    """

    def __init__(self, shared_memory: Any = None) -> None:
        self._shared_memory = shared_memory
        self._access_policies: dict[str, dict[str, AccessLevel]] = {}  # ns → agent_id → level
        self._stats_writes = 0
        self._stats_reads = 0
        self._stats_evictions = 0

    # ── Access Control ──

    def grant_access(self, agent_id: str, namespace: str, level: AccessLevel) -> None:
        """Grant an agent access to a namespace."""
        if namespace not in self._access_policies:
            self._access_policies[namespace] = {}
        self._access_policies[namespace][agent_id] = level

    def revoke_access(self, agent_id: str, namespace: str) -> None:
        """Revoke an agent's access to a namespace."""
        if namespace in self._access_policies:
            self._access_policies[namespace].pop(agent_id, None)

    def check_access(self, agent_id: str, namespace: str,
                     required_level: AccessLevel) -> bool:
        """Check if an agent has sufficient access to a namespace."""
        ns_policy = self._access_policies.get(namespace, {})
        agent_level = ns_policy.get(agent_id, AccessLevel.NONE)

        level_order = {AccessLevel.NONE: 0, AccessLevel.READ: 1,
                       AccessLevel.WRITE: 2, AccessLevel.ADMIN: 3}
        return level_order.get(agent_level, 0) >= level_order.get(required_level, 0)

    # ── Read Operations ──

    async def get(self, agent_id: str, key: str,
                  namespace: str = "default") -> Optional[Any]:
        """Read a value from shared memory (with access check)."""
        if not self.check_access(agent_id, namespace, AccessLevel.READ):
            logger.warning("Access denied: %s read %s/%s", agent_id, namespace, key)
            return None

        self._stats_reads += 1

        if self._shared_memory is None:
            return None

        entry = await self._shared_memory.get(key, namespace)
        if entry is None:
            return None

        if isinstance(entry, MemoryEntry):
            if entry.is_expired():
                await self._shared_memory.delete(key, namespace)
                self._stats_evictions += 1
                return None
            return entry.value

        return entry

    async def get_entry(self, agent_id: str, key: str,
                        namespace: str = "default") -> Optional[MemoryEntry]:
        """Read the full memory entry with metadata."""
        if not self.check_access(agent_id, namespace, AccessLevel.READ):
            return None

        self._stats_reads += 1

        if self._shared_memory is None:
            return None

        entry = await self._shared_memory.get_entry(key, namespace)
        if isinstance(entry, MemoryEntry) and entry.is_expired():
            await self._shared_memory.delete(key, namespace)
            self._stats_evictions += 1
            return None

        return entry

    async def get_many(self, agent_id: str, keys: list[str],
                       namespace: str = "default") -> dict[str, Any]:
        """Read multiple keys atomically."""
        results = {}
        for key in keys:
            val = await self.get(agent_id, key, namespace)
            if val is not None:
                results[key] = val
        return results

    # ── Write Operations ──

    async def put(self, agent_id: str, key: str, value: Any,
                  namespace: str = "default",
                  ttl_seconds: int = 0,
                  tags: Optional[list[str]] = None) -> bool:
        """Write a value to shared memory (with access check)."""
        if not self.check_access(agent_id, namespace, AccessLevel.WRITE):
            logger.warning("Access denied: %s write %s/%s", agent_id, namespace, key)
            return False

        self._stats_writes += 1

        if self._shared_memory is None:
            return False

        entry = MemoryEntry(
            key=key,
            value=value,
            namespace=namespace,
            created_by=agent_id,
            ttl_seconds=ttl_seconds,
            tags=tags or [],
        )

        # Preserve version if updating
        existing = await self._shared_memory.get_entry(key, namespace)
        if existing is not None:
            entry.version = existing.version + 1

        return await self._shared_memory.put(key, entry, namespace)

    async def put_many(self, agent_id: str, entries: dict[str, Any],
                       namespace: str = "default",
                       ttl_seconds: int = 0) -> bool:
        """Write multiple entries atomically."""
        if not self.check_access(agent_id, namespace, AccessLevel.WRITE):
            return False

        self._stats_writes += len(entries)

        if self._shared_memory is None:
            return False

        all_ok = True
        for key, value in entries.items():
            ok = await self.put(agent_id, key, value, namespace, ttl_seconds)
            all_ok = all_ok and ok
        return all_ok

    # ── Delete ──

    async def delete(self, agent_id: str, key: str,
                     namespace: str = "default") -> bool:
        """Delete a key from shared memory."""
        if not self.check_access(agent_id, namespace, AccessLevel.WRITE):
            return False

        if self._shared_memory is None:
            return False

        return await self._shared_memory.delete(key, namespace)

    # ── Query ──

    async def list_keys(self, agent_id: str,
                        namespace: str = "default",
                        tag_filter: Optional[str] = None) -> list[str]:
        """List all keys in a namespace, optionally filtered by tag."""
        if not self.check_access(agent_id, namespace, AccessLevel.READ):
            return []

        if self._shared_memory is None:
            return []

        keys = await self._shared_memory.list_keys(namespace)
        if tag_filter is None:
            return keys

        # Filter by tag
        filtered = []
        for key in keys:
            entry = await self._shared_memory.get_entry(key, namespace)
            if entry and tag_filter in (entry.tags if isinstance(entry, MemoryEntry) else []):
                filtered.append(key)
        return filtered

    async def search_by_tag(self, agent_id: str, tag: str) -> dict[str, Any]:
        """Search across all namespaces for entries with a given tag."""
        results = {}
        if self._shared_memory is None:
            return results

        for namespace in self._access_policies:
            if not self.check_access(agent_id, namespace, AccessLevel.READ):
                continue
            keys = await self._shared_memory.list_keys(namespace)
            for key in keys:
                entry = await self._shared_memory.get_entry(key, namespace)
                if isinstance(entry, MemoryEntry) and tag in entry.tags:
                    results[f"{namespace}/{key}"] = entry.value
        return results

    # ── Namespace Management ──

    async def clear_namespace(self, agent_id: str, namespace: str) -> int:
        """Clear all entries in a namespace. Returns count of deleted entries."""
        if not self.check_access(agent_id, namespace, AccessLevel.ADMIN):
            return 0

        if self._shared_memory is None:
            return 0

        keys = await self._shared_memory.list_keys(namespace)
        deleted = 0
        for key in keys:
            if await self._shared_memory.delete(key, namespace):
                deleted += 1
        return deleted

    # ── Stats ──

    @property
    def writes(self) -> int:
        return self._stats_writes

    @property
    def reads(self) -> int:
        return self._stats_reads

    @property
    def evictions(self) -> int:
        return self._stats_evictions
