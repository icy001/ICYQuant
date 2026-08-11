"""Shared Memory — inter-agent shared context with segment-based storage and query.

Pipeline:
    Agent writes context
        -> SharedMemory.write() (create/update segment)
        -> index by key / namespace / agent_id
        -> MessageBus (notify other agents of update)

    Agent reads context
        -> SharedMemory.read() (retrieve by key)
        -> SharedMemory.query() (search by namespace / agent / tags)
        -> return MemorySegment(s)

Provides a unified memory API for all agents to share context, avoiding
redundant computation and enabling collaborative reasoning.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.collaboration.message_bus import MessageBus, Message, MessageType

logger = logging.getLogger(__name__)


class MemorySegmentType(str, Enum):
    """Types of shared memory segments."""
    MARKET_CONTEXT = "market_context"
    RESEARCH_CONTEXT = "research_context"
    RISK_CONTEXT = "risk_context"
    STRATEGY_CONTEXT = "strategy_context"
    PORTFOLIO_CONTEXT = "portfolio_context"
    EXECUTION_CONTEXT = "execution_context"
    OBSERVATION = "observation"
    DECISION = "decision"
    GENERAL = "general"


@dataclass
class MemorySegment:
    """A segment of shared memory.

    Attributes:
        segment_id: Unique segment identifier.
        key: Logical key for retrieval.
        namespace: Logical namespace (e.g. agent domain).
        segment_type: Type of memory segment.
        data: The stored data.
        owner_agent_id: Agent that created this segment.
        tags: Searchable tags.
        version: Monotonic version counter.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        ttl_seconds: Time-to-live (None = permanent).
    """

    segment_id: str = field(default_factory=lambda: uuid4().hex)
    key: str = ""
    namespace: str = ""
    segment_type: MemorySegmentType = MemorySegmentType.GENERAL
    data: Any = None
    owner_agent_id: str = ""
    tags: List[str] = field(default_factory=list)
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: Optional[float] = None

    @property
    def is_expired(self) -> bool:
        """Return whether the segment has exceeded its TTL."""
        if self.ttl_seconds is None:
            return False
        return (datetime.now(timezone.utc) - self.updated_at).total_seconds() > self.ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        """Return segment metadata as a dictionary."""
        return {
            "segment_id": self.segment_id,
            "key": self.key,
            "namespace": self.namespace,
            "segment_type": self.segment_type.value,
            "owner_agent_id": self.owner_agent_id,
            "tags": self.tags,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class MemoryQuery:
    """Query parameters for searching shared memory.

    Attributes:
        key: Exact key match.
        namespace: Filter by namespace.
        segment_type: Filter by segment type.
        owner_agent_id: Filter by owner agent.
        tags: Filter by tags (AND match).
        limit: Maximum results.
    """

    key: Optional[str] = None
    namespace: Optional[str] = None
    segment_type: Optional[MemorySegmentType] = None
    owner_agent_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    limit: int = 50


class SharedMemory:
    """Inter-agent shared memory for collaborative context.

    Provides a unified key-value store with namespace, tagging, and
    TTL support. All agents read and write through the same API,
    enabling seamless context sharing across the multi-agent system.

    Supports:
        - Key-based read/write with namespace isolation
        - Segment type categorization
        - Tag-based search
        - TTL-based expiry
        - Version tracking (optimistic concurrency)
        - Change notification via MessageBus
        - Agent-ownership tracking

    Usage:
        memory = SharedMemory(message_bus)
        await memory.initialize()
        await memory.write("market.snapshot", data, namespace="market", ...)
        segment = memory.read("market.snapshot")
        results = memory.query(MemoryQuery(namespace="market"))
    """

    def __init__(self, message_bus: MessageBus, max_segments: int = 1000) -> None:
        """Initialize shared memory.

        Args:
            message_bus: Message bus for change notifications.
            max_segments: Maximum number of memory segments.
        """
        self._message_bus: MessageBus = message_bus
        self._max_segments: int = max_segments
        self._segments: Dict[str, MemorySegment] = {}  # key -> segment
        self._id_index: Dict[str, str] = {}  # segment_id -> key
        self._initialized: bool = False
        logger.info("SharedMemory created (max_segments=%d)", max_segments)

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize shared memory."""
        if self._initialized:
            logger.warning("SharedMemory already initialized")
            return
        self._initialized = True
        logger.info("SharedMemory initialized")

    async def shutdown(self) -> None:
        """Shut down and clear all memory."""
        if not self._initialized:
            return
        self._segments.clear()
        self._id_index.clear()
        self._initialized = False
        logger.info("SharedMemory shutdown complete")

    # ── Write ──

    async def write(
        self,
        key: str,
        data: Any,
        namespace: str = "default",
        segment_type: MemorySegmentType = MemorySegmentType.GENERAL,
        owner_agent_id: str = "",
        tags: Optional[List[str]] = None,
        ttl_seconds: Optional[float] = None,
    ) -> MemorySegment:
        """Write a memory segment.

        If a segment with the same key exists, it is updated (version incremented).

        Args:
            key: Logical key for retrieval.
            data: The data to store.
            namespace: Logical namespace.
            segment_type: Type of memory segment.
            owner_agent_id: Agent that owns this segment.
            tags: Searchable tags.
            ttl_seconds: Time-to-live in seconds.

        Returns:
            The created or updated memory segment.
        """
        if not self._initialized:
            raise RuntimeError("SharedMemory not initialized")

        # Enforce max segments
        if len(self._segments) >= self._max_segments and key not in self._segments:
            self._evict_oldest()

        now = datetime.now(timezone.utc)

        if key in self._segments:
            # Update existing
            segment = self._segments[key]
            segment.data = data
            segment.version += 1
            segment.updated_at = now
            segment.ttl_seconds = ttl_seconds
            if tags is not None:
                segment.tags = tags
            logger.debug("Memory updated: %s (v%d)", key, segment.version)
        else:
            # Create new
            segment = MemorySegment(
                key=key,
                namespace=namespace,
                segment_type=segment_type,
                data=data,
                owner_agent_id=owner_agent_id,
                tags=tags or [],
                ttl_seconds=ttl_seconds,
            )
            self._segments[key] = segment
            self._id_index[segment.segment_id] = key
            logger.debug("Memory written: %s", key)

        # Notify other agents
        await self._notify_update(segment)

        return segment

    # ── Read ──

    def read(self, key: str) -> Optional[MemorySegment]:
        """Read a memory segment by key.

        Args:
            key: The segment key.

        Returns:
            The memory segment, or None if not found or expired.
        """
        segment = self._segments.get(key)
        if segment and segment.is_expired:
            del self._segments[key]
            return None
        return segment

    # ── Query ──

    def query(self, query: MemoryQuery) -> List[MemorySegment]:
        """Search memory segments matching query parameters.

        Args:
            query: Search parameters.

        Returns:
            List of matching memory segments.
        """
        results: List[MemorySegment] = []

        for segment in self._segments.values():
            if segment.is_expired:
                continue
            if query.key is not None and segment.key != query.key:
                continue
            if query.namespace is not None and segment.namespace != query.namespace:
                continue
            if query.segment_type is not None and segment.segment_type != query.segment_type:
                continue
            if query.owner_agent_id is not None and segment.owner_agent_id != query.owner_agent_id:
                continue
            if query.tags:
                if not all(t in segment.tags for t in query.tags):
                    continue
            results.append(segment)

        results.sort(key=lambda s: s.updated_at, reverse=True)
        return results[:query.limit]

    # ── Delete ──

    def delete(self, key: str) -> bool:
        """Delete a memory segment by key.

        Args:
            key: The segment key.

        Returns:
            True if deleted, False if not found.
        """
        segment = self._segments.pop(key, None)
        if segment:
            self._id_index.pop(segment.segment_id, None)
            logger.debug("Memory deleted: %s", key)
            return True
        return False

    def clear_namespace(self, namespace: str) -> int:
        """Delete all segments in a namespace.

        Args:
            namespace: The namespace to clear.

        Returns:
            Number of segments deleted.
        """
        keys_to_delete = [
            k for k, s in self._segments.items()
            if s.namespace == namespace
        ]
        for key in keys_to_delete:
            self.delete(key)
        return len(keys_to_delete)

    # ── Helpers ──

    async def _notify_update(self, segment: MemorySegment) -> None:
        """Notify other agents of a memory update via the message bus.

        Args:
            segment: The updated segment.
        """
        try:
            msg = Message(
                msg_type=MessageType.PUBLISH,
                topic="memory.updated",
                sender_id=segment.owner_agent_id,
                payload={
                    "key": segment.key,
                    "namespace": segment.namespace,
                    "version": segment.version,
                },
            )
            await self._message_bus.publish(msg)
        except Exception:
            logger.exception("Failed to notify memory update for %s", segment.key)

    def _evict_oldest(self) -> None:
        """Evict the oldest segment to make room."""
        if not self._segments:
            return
        oldest_key = min(
            self._segments.keys(),
            key=lambda k: self._segments[k].updated_at,
        )
        self.delete(oldest_key)
        logger.debug("Evicted oldest memory segment: %s", oldest_key)

    # ── Properties ──

    @property
    def count(self) -> int:
        """Return the number of memory segments."""
        return len(self._segments)

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of shared memory state.

        Returns:
            Dict with segment count, namespace breakdown, and capacity.
        """
        namespace_counts: Dict[str, int] = {}
        type_counts: Dict[str, int] = {}
        for s in self._segments.values():
            namespace_counts[s.namespace] = namespace_counts.get(s.namespace, 0) + 1
            type_counts[s.segment_type.value] = type_counts.get(s.segment_type.value, 0) + 1

        return {
            "initialized": self._initialized,
            "total_segments": len(self._segments),
            "max_segments": self._max_segments,
            "namespace_breakdown": namespace_counts,
            "type_breakdown": type_counts,
        }
