"""Tool Cache — result caching for idempotent tool calls.

Pipeline:
    Tool Request -> Hash (tool_name + params) -> Cache Lookup
        -> Cache Hit: return cached result
        -> Cache Miss: execute tool, store result
        -> Response

Reduces redundant tool calls and improves response time for
repeated idempotent operations.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── CacheEntry ──

@dataclass
class CacheEntry:
    """A cached tool result entry."""

    key: str
    tool_name: str
    result_data: Any
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: float = 300.0  # 5 minutes default
    access_count: int = 0
    last_accessed_at: Optional[datetime] = None

    @property
    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        if self.ttl_seconds <= 0:
            return False
        age = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return age >= self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        """Age of the entry in seconds."""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()

    def access(self) -> None:
        """Record an access to this entry."""
        self.access_count += 1
        self.last_accessed_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "key": self.key,
            "tool_name": self.tool_name,
            "age_seconds": round(self.age_seconds, 1),
            "ttl_seconds": self.ttl_seconds,
            "access_count": self.access_count,
            "is_expired": self.is_expired,
            "created_at": self.created_at.isoformat(),
            "last_accessed_at": (
                self.last_accessed_at.isoformat() if self.last_accessed_at else None
            ),
        }


# ── CacheStats ──

@dataclass
class CacheStats:
    """Cache performance statistics."""

    total_lookups: int = 0
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0

    @property
    def hit_ratio(self) -> float:
        """Cache hit ratio (0.0 to 1.0)."""
        if self.total_lookups == 0:
            return 0.0
        return self.hits / self.total_lookups

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total_lookups": self.total_lookups,
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": round(self.hit_ratio, 4),
            "evictions": self.evictions,
            "expirations": self.expirations,
        }


# ── ToolCache ──

class ToolCache:
    """Result cache for idempotent tool calls.

    Caches results for idempotent tools to reduce redundant execution.
    Uses a hash of (tool_name + sorted params) as the cache key.

    Supports:
        - TTL-based expiration
        - Max size enforcement with LRU eviction
        - Per-tool and global cache controls
        - Hit/miss statistics
        - Cache key generation

    Usage:
        cache = ToolCache(max_size=1000, default_ttl_seconds=300)
        await cache.initialize()
        entry = cache.get("backtest.run", {"strategy_id": "s1"})
        if entry:
            return entry.result_data
        result = await execute(...)
        cache.put("backtest.run", {"strategy_id": "s1"}, result)
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl_seconds: float = 300.0,
    ) -> None:
        """Initialize the cache.

        Args:
            max_size: Maximum number of cached entries.
            default_ttl_seconds: Default TTL for cached entries.
        """
        self._max_size = max_size
        self._default_ttl_seconds = default_ttl_seconds

        self._entries: Dict[str, CacheEntry] = {}
        self._stats = CacheStats()
        self._disabled_tools: set = set()  # Tools excluded from caching

        self._initialized: bool = False
        logger.info(
            f"ToolCache created (max_size={max_size}, default_ttl={default_ttl_seconds}s)"
        )

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the cache."""
        self._initialized = True
        logger.info("ToolCache initialized")

    async def shutdown(self) -> None:
        """Shutdown the cache."""
        self._entries.clear()
        self._initialized = False
        logger.info("ToolCache shutdown complete")

    # ── Cache Operations ──

    def get(self, tool_name: str, params: Dict[str, Any]) -> Optional[CacheEntry]:
        """Get a cached result for a tool call.

        Args:
            tool_name: The tool name.
            params: The tool parameters.

        Returns:
            A CacheEntry if found and not expired, None otherwise.
        """
        if tool_name in self._disabled_tools:
            return None

        self._stats.total_lookups += 1
        key = self._make_key(tool_name, params)
        entry = self._entries.get(key)

        if entry is None:
            self._stats.misses += 1
            return None

        if entry.is_expired:
            self._remove_entry(key)
            self._stats.expirations += 1
            self._stats.misses += 1
            return None

        entry.access()
        self._stats.hits += 1
        logger.debug(f"Cache hit: {tool_name} (key={key[:16]}...)")
        return entry

    def put(
        self,
        tool_name: str,
        params: Dict[str, Any],
        result_data: Any,
        ttl_seconds: Optional[float] = None,
    ) -> CacheEntry:
        """Cache a tool result.

        Args:
            tool_name: The tool name.
            params: The tool parameters.
            result_data: The result data to cache.
            ttl_seconds: Optional custom TTL.

        Returns:
            The created CacheEntry.
        """
        if tool_name in self._disabled_tools:
            return CacheEntry(key="", tool_name=tool_name, result_data=None)

        # Evict if at capacity
        if len(self._entries) >= self._max_size:
            self._evict_lru()

        key = self._make_key(tool_name, params)
        entry = CacheEntry(
            key=key,
            tool_name=tool_name,
            result_data=result_data,
            ttl_seconds=ttl_seconds if ttl_seconds is not None else self._default_ttl_seconds,
        )
        self._entries[key] = entry
        logger.debug(f"Cache put: {tool_name} (key={key[:16]}..., ttl={entry.ttl_seconds}s)")
        return entry

    def invalidate(self, tool_name: str, params: Optional[Dict[str, Any]] = None) -> int:
        """Invalidate cached entries.

        Args:
            tool_name: The tool name to invalidate.
            params: Optional specific params to invalidate.
                    If None, invalidates all entries for the tool.

        Returns:
            Number of entries invalidated.
        """
        count = 0
        if params is not None:
            key = self._make_key(tool_name, params)
            if key in self._entries:
                self._remove_entry(key)
                count = 1
        else:
            keys_to_remove = [
                k for k, e in self._entries.items() if e.tool_name == tool_name
            ]
            for k in keys_to_remove:
                self._remove_entry(k)
                count += 1

        logger.info(f"Cache invalidated: {count} entries for {tool_name}")
        return count

    def clear(self) -> None:
        """Clear all cached entries."""
        count = len(self._entries)
        self._entries.clear()
        logger.info(f"Cache cleared: {count} entries")

    def disable_tool(self, tool_name: str) -> None:
        """Disable caching for a specific tool.

        Args:
            tool_name: The tool to disable caching for.
        """
        self._disabled_tools.add(tool_name)
        self.invalidate(tool_name)
        logger.info(f"Cache disabled for tool: {tool_name}")

    def enable_tool(self, tool_name: str) -> None:
        """Enable caching for a specific tool.

        Args:
            tool_name: The tool to enable caching for.
        """
        self._disabled_tools.discard(tool_name)
        logger.info(f"Cache enabled for tool: {tool_name}")

    # ── Key Generation ──

    @staticmethod
    def _make_key(tool_name: str, params: Dict[str, Any]) -> str:
        """Generate a cache key from tool name and params.

        Args:
            tool_name: The tool name.
            params: The tool parameters.

        Returns:
            A unique cache key string.
        """
        sorted_params = json.dumps(params, sort_keys=True, default=str)
        raw = f"{tool_name}:{sorted_params}"
        return hashlib.sha256(raw.encode()).hexdigest()

    # ── Private Methods ──

    def _remove_entry(self, key: str) -> None:
        """Remove a cache entry.

        Args:
            key: The cache key.
        """
        self._entries.pop(key, None)

    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if not self._entries:
            return

        # Find the entry with the oldest last_accessed_at or created_at
        oldest_key = None
        oldest_time: Optional[datetime] = None

        for key, entry in self._entries.items():
            access_time = entry.last_accessed_at or entry.created_at
            if oldest_time is None or access_time < oldest_time:
                oldest_time = access_time
                oldest_key = key

        if oldest_key:
            self._remove_entry(oldest_key)
            self._stats.evictions += 1
            logger.debug(f"Cache LRU eviction: {oldest_key[:16]}...")

    # ── Cleanup ──

    async def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed.
        """
        expired_keys = [k for k, e in self._entries.items() if e.is_expired]
        for k in expired_keys:
            self._remove_entry(k)
            self._stats.expirations += 1

        if expired_keys:
            logger.info(f"Cache cleanup: {len(expired_keys)} expired entries removed")
        return len(expired_keys)

    # ── Status ──

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        return len(self._entries)

    def get_summary(self) -> Dict[str, Any]:
        """Get cache status summary."""
        return {
            "size": self.size,
            "max_size": self._max_size,
            "default_ttl_seconds": self._default_ttl_seconds,
            "disabled_tools": list(self._disabled_tools),
            "stats": self._stats.to_dict(),
            "initialized": self._initialized,
        }
