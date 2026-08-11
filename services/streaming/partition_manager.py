"""
Partition Manager — topic partition lifecycle, assignment, and
rebalancing for the streaming platform.

Commit 16 Part 1.4
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PartitionStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    REBALANCING = "rebalancing"
    INACTIVE = "inactive"


@dataclass
class Partition:
    """A single partition within a topic."""
    topic: str
    partition_id: int
    status: PartitionStatus = PartitionStatus.CREATED
    leader_id: str = ""
    replicas: list[str] = field(default_factory=list)
    offset_start: int = 0
    offset_end: int = 0
    events_count: int = 0
    bytes_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PartitionAssignment:
    """Consumer assignment to a partition."""
    topic: str
    partition_id: int
    consumer_id: str
    assigned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    current_offset: int = 0


class PartitionManager:
    """
    Manages topic partitions including creation, assignment,
    rebalancing, and offset tracking.

    Features:
    - Dynamic partition creation
    - Key-based partition routing (consistent hashing)
    - Consumer group assignment
    - Partition rebalancing
    - Offset tracking per consumer

    Usage::

        pm = PartitionManager(default_partitions=4)
        await pm.create_partitions("market.tick", count=8)
        partition_id = pm.route("market.tick", "BTC/USDT")
        await pm.assign("market.tick", 0, "consumer-1")
    """

    def __init__(
        self,
        default_partitions: int = 4,
        max_partitions_per_topic: int = 256,
    ) -> None:
        self.default_partitions = default_partitions
        self.max_partitions_per_topic = max_partitions_per_topic
        self._partitions: dict[str, dict[int, Partition]] = {}
        self._assignments: dict[str, dict[int, list[PartitionAssignment]]] = {}
        self._lock = asyncio.Lock()

    async def create_partitions(self, topic: str, count: int) -> list[Partition]:
        """Create partitions for a topic."""
        async with self._lock:
            if count > self.max_partitions_per_topic:
                raise ValueError(
                    f"Partition count {count} exceeds max {self.max_partitions_per_topic}"
                )

            if topic not in self._partitions:
                self._partitions[topic] = {}

            existing = self._partitions[topic]
            if len(existing) >= count:
                return list(existing.values())

            partitions = []
            for i in range(count):
                if i not in existing:
                    partition = Partition(
                        topic=topic,
                        partition_id=i,
                        status=PartitionStatus.ACTIVE,
                    )
                    existing[i] = partition
                    partitions.append(partition)
                else:
                    partitions.append(existing[i])

            logger.info(
                "Created %d partitions for topic: %s", count, topic,
            )
            return partitions

    def route(self, topic: str, key: str) -> int:
        """Route a key to a partition using consistent hashing."""
        partitions = self._partitions.get(topic, {})
        if not partitions:
            return 0

        hash_val = int(hashlib.md5(key.encode()).hexdigest(), 16)
        return hash_val % len(partitions)

    async def get_partition(self, topic: str, partition_id: int) -> Optional[Partition]:
        """Get a specific partition."""
        topic_partitions = self._partitions.get(topic, {})
        return topic_partitions.get(partition_id)

    async def list_partitions(self, topic: str) -> list[Partition]:
        """List all partitions for a topic."""
        return list(self._partitions.get(topic, {}).values())

    async def assign(
        self,
        topic: str,
        partition_id: int,
        consumer_id: str,
    ) -> PartitionAssignment:
        """Assign a consumer to a partition."""
        if topic not in self._assignments:
            self._assignments[topic] = {}

        if partition_id not in self._assignments[topic]:
            self._assignments[topic][partition_id] = []

        assignment = PartitionAssignment(
            topic=topic,
            partition_id=partition_id,
            consumer_id=consumer_id,
        )
        self._assignments[topic][partition_id].append(assignment)

        # Update partition status
        partition = await self.get_partition(topic, partition_id)
        if partition:
            partition.status = PartitionStatus.ACTIVE

        return assignment

    async def unassign(self, topic: str, partition_id: int, consumer_id: str) -> bool:
        """Remove a consumer assignment."""
        assignments = self._assignments.get(topic, {}).get(partition_id, [])
        for a in assignments:
            if a.consumer_id == consumer_id:
                assignments.remove(a)
                return True
        return False

    async def rebalance(self, topic: str, consumers: list[str]) -> list[PartitionAssignment]:
        """Rebalance partitions across consumers."""
        partitions = await self.list_partitions(topic)
        if not consumers:
            return []

        assignments = []
        for i, partition in enumerate(partitions):
            consumer_idx = i % len(consumers)
            consumer_id = consumers[consumer_idx]
            assignment = await self.assign(topic, partition.partition_id, consumer_id)
            assignments.append(assignment)

        logger.info(
            "Rebalanced topic %s: %d partitions → %d consumers",
            topic, len(partitions), len(consumers),
        )
        return assignments

    async def commit_offset(
        self, topic: str, partition_id: int, consumer_id: str, offset: int
    ) -> bool:
        """Commit a consumer offset for a partition."""
        assignments = self._assignments.get(topic, {}).get(partition_id, [])
        for a in assignments:
            if a.consumer_id == consumer_id:
                a.current_offset = offset

                # Update partition end offset
                partition = await self.get_partition(topic, partition_id)
                if partition:
                    partition.offset_end = max(partition.offset_end, offset)

                return True
        return False

    async def get_consumer_offset(
        self, topic: str, partition_id: int, consumer_id: str
    ) -> Optional[int]:
        """Get the current offset for a consumer."""
        assignments = self._assignments.get(topic, {}).get(partition_id, [])
        for a in assignments:
            if a.consumer_id == consumer_id:
                return a.current_offset
        return None

    async def delete_partitions(self, topic: str) -> int:
        """Delete all partitions for a topic."""
        async with self._lock:
            count = len(self._partitions.get(topic, {}))
            self._partitions.pop(topic, None)
            self._assignments.pop(topic, None)
            return count

    async def summary(self, topic: str) -> dict[str, Any]:
        """Get partition summary for a topic."""
        partitions = await self.list_partitions(topic)
        assignments = self._assignments.get(topic, {})

        total_events = sum(p.events_count for p in partitions)
        total_bytes = sum(p.bytes_count for p in partitions)
        assigned_consumers = set()
        for part_assignments in assignments.values():
            for a in part_assignments:
                assigned_consumers.add(a.consumer_id)

        return {
            "topic": topic,
            "partition_count": len(partitions),
            "total_events": total_events,
            "total_bytes": total_bytes,
            "assigned_consumers": len(assigned_consumers),
            "partitions": [
                {
                    "id": p.partition_id,
                    "status": p.status.value,
                    "events": p.events_count,
                    "offset_range": f"{p.offset_start}-{p.offset_end}",
                }
                for p in partitions
            ],
        }
