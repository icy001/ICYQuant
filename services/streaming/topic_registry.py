"""
Topic Registry — unified topic namespace management for the streaming
platform with dynamic registration, partitioning, and status tracking.

Commit 16 Part 1.4
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TopicStatus(str, Enum):
    CREATING = "creating"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETING = "deleting"
    DELETED = "deleted"
    ERROR = "error"


@dataclass
class TopicEntry:
    """Metadata entry for a registered topic."""
    name: str
    partition_count: int
    status: TopicStatus = TopicStatus.CREATING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    subscribers: int = 0
    total_published: int = 0
    total_bytes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: Optional[str] = None


class TopicRegistry:
    """
    Unified topic namespace for the streaming platform.

    Manages topic registration, lifecycle, and metadata across
    all producers and consumers with dynamic topic management.

    Predefined topics:
        market.tick, market.trade, market.orderbook
        strategy.signal, risk.alert
        oms.order, ems.execution
        portfolio.update

    Usage::

        registry = TopicRegistry()
        await registry.initialize()
        entry = await registry.register("market.tick", partitions=4)
        topics = await registry.list_all()
    """

    PREDEFINED_TOPICS = [
        ("market.tick", 8),
        ("market.trade", 8),
        ("market.orderbook", 8),
        ("strategy.signal", 4),
        ("risk.alert", 4),
        ("oms.order", 4),
        ("ems.execution", 4),
        ("portfolio.update", 4),
    ]

    def __init__(self, max_topics: int = 1000) -> None:
        self.max_topics = max_topics
        self._topics: dict[str, TopicEntry] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the topic registry with predefined topics."""
        for name, partitions in self.PREDEFINED_TOPICS:
            await self.register(name, partitions=partitions, status=TopicStatus.ACTIVE)
        logger.info("TopicRegistry initialized with %d predefined topics.", len(self.PREDEFINED_TOPICS))

    async def register(
        self,
        name: str,
        partitions: int = 4,
        *,
        status: TopicStatus = TopicStatus.CREATING,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TopicEntry:
        """Register a new topic."""
        async with self._lock:
            if name in self._topics:
                existing = self._topics[name]
                if existing.status == TopicStatus.DELETED:
                    existing.status = status
                    existing.partition_count = partitions
                    existing.updated_at = datetime.now(timezone.utc)
                return existing

            if len(self._topics) >= self.max_topics:
                raise RuntimeError(f"Max topics reached ({self.max_topics})")

            entry = TopicEntry(
                name=name,
                partition_count=partitions,
                status=status,
                metadata=metadata or {},
            )
            self._topics[name] = entry
            logger.info("Topic registered: %s (%d partitions)", name, partitions)
            return entry

    async def get(self, name: str) -> Optional[TopicEntry]:
        """Get a topic by name."""
        return self._topics.get(name)

    async def list_all(self) -> list[TopicEntry]:
        """List all registered topics."""
        return list(self._topics.values())

    async def list_active(self) -> list[TopicEntry]:
        """List only active topics."""
        return [t for t in self._topics.values() if t.status == TopicStatus.ACTIVE]

    async def update_status(self, name: str, status: TopicStatus) -> bool:
        """Update the status of a topic."""
        entry = self._topics.get(name)
        if entry:
            entry.status = status
            entry.updated_at = datetime.now(timezone.utc)
            return True
        return False

    async def increment_published(self, name: str, count: int = 1, bytes_written: int = 0) -> None:
        """Increment published event counters for a topic."""
        entry = self._topics.get(name)
        if entry:
            entry.total_published += count
            entry.total_bytes += bytes_written
            entry.updated_at = datetime.now(timezone.utc)

    async def update_subscribers(self, name: str, count: int) -> None:
        """Update subscriber count for a topic."""
        entry = self._topics.get(name)
        if entry:
            entry.subscribers = count

    async def set_schema_version(self, name: str, version: str) -> bool:
        """Set the schema version for a topic."""
        entry = self._topics.get(name)
        if entry:
            entry.schema_version = version
            return True
        return False

    async def delete(self, name: str) -> bool:
        """Delete a topic."""
        async with self._lock:
            entry = self._topics.get(name)
            if entry:
                entry.status = TopicStatus.DELETED
                entry.updated_at = datetime.now(timezone.utc)
                logger.info("Topic deleted: %s", name)
                return True
        return False

    async def count(self) -> int:
        """Count total registered topics."""
        return len(self._topics)

    async def count_active(self) -> int:
        """Count active topics."""
        return sum(1 for t in self._topics.values() if t.status == TopicStatus.ACTIVE)

    async def exists(self, name: str) -> bool:
        """Check if a topic exists."""
        return name in self._topics and self._topics[name].status != TopicStatus.DELETED
