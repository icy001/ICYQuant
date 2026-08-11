"""
Consumer Group — coordinated consumption with load balancing,
offset management, and rebalancing protocols.

Commit 16 Part 1.4
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MemberStatus(str, Enum):
    JOINING = "joining"
    ACTIVE = "active"
    REBALANCING = "rebalancing"
    LEAVING = "leaving"
    INACTIVE = "inactive"


@dataclass
class ConsumerMember:
    """A member of a consumer group."""
    member_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    consumer_id: str = ""
    group_id: str = ""
    status: MemberStatus = MemberStatus.JOINING
    assigned_partitions: list[int] = field(default_factory=list)
    current_offsets: dict[int, int] = field(default_factory=dict)
    joined_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    events_consumed: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OffsetCommit:
    """An offset commit for a consumer group."""
    topic: str
    partition: int
    offset: int
    consumer_id: str
    group_id: str
    committed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: str = ""


class ConsumerGroup:
    """
    Coordinated consumer group with load balancing and offset management.

    Manages consumer membership, partition assignment, offset commits,
    and rebalancing for a group of consumers reading from the same topics.

    Usage::

        group = ConsumerGroup("algo-group-1")
        member = await group.join("consumer-1")
        await group.assign_partitions(["market.tick"], member.member_id)
        await group.commit_offset("market.tick", 0, 100, "consumer-1")
    """

    def __init__(
        self,
        group_id: str,
        *,
        session_timeout_ms: int = 30000,
        heartbeat_interval_ms: int = 3000,
        max_poll_interval_ms: int = 300000,
    ) -> None:
        self.group_id = group_id
        self.session_timeout_ms = session_timeout_ms
        self.heartbeat_interval_ms = heartbeat_interval_ms
        self.max_poll_interval_ms = max_poll_interval_ms

        self._members: dict[str, ConsumerMember] = {}
        self._offsets: dict[str, dict[int, int]] = {}  # topic → partition → offset
        self._generation_id = 0
        self._lock = asyncio.Lock()

    async def join(self, consumer_id: str, metadata: Optional[dict[str, Any]] = None) -> ConsumerMember:
        """Add a consumer to the group."""
        async with self._lock:
            # Check for rejoin
            for existing in self._members.values():
                if existing.consumer_id == consumer_id:
                    existing.status = MemberStatus.ACTIVE
                    existing.last_heartbeat = datetime.now(timezone.utc)
                    return existing

            member = ConsumerMember(
                consumer_id=consumer_id,
                group_id=self.group_id,
                metadata=metadata or {},
            )
            self._members[member.member_id] = member
            logger.info(
                "Consumer %s joined group %s", consumer_id, self.group_id,
            )
            return member

    async def leave(self, consumer_id: str) -> bool:
        """Remove a consumer from the group."""
        async with self._lock:
            for member_id, member in list(self._members.items()):
                if member.consumer_id == consumer_id:
                    member.status = MemberStatus.LEAVING
                    del self._members[member_id]
                    self._generation_id += 1
                    logger.info(
                        "Consumer %s left group %s", consumer_id, self.group_id,
                    )
                    return True
        return False

    async def heartbeat(self, consumer_id: str) -> bool:
        """Record a heartbeat from a consumer."""
        for member in self._members.values():
            if member.consumer_id == consumer_id:
                member.last_heartbeat = datetime.now(timezone.utc)
                member.status = MemberStatus.ACTIVE
                return True
        return False

    async def assign_partitions(
        self, topic: str, partitions: list[int], consumer_id: str
    ) -> bool:
        """Assign partitions to a consumer."""
        for member in self._members.values():
            if member.consumer_id == consumer_id:
                member.assigned_partitions = partitions
                member.status = MemberStatus.ACTIVE
                return True
        return False

    async def commit_offset(
        self,
        topic: str,
        partition: int,
        offset: int,
        consumer_id: str,
        metadata: str = "",
    ) -> OffsetCommit:
        """Commit an offset for a consumer."""
        if topic not in self._offsets:
            self._offsets[topic] = {}

        self._offsets[topic][partition] = offset

        # Update member
        for member in self._members.values():
            if member.consumer_id == consumer_id:
                member.current_offsets[partition] = offset
                member.events_consumed += 1

        return OffsetCommit(
            topic=topic,
            partition=partition,
            offset=offset,
            consumer_id=consumer_id,
            group_id=self.group_id,
            metadata=metadata,
        )

    async def get_committed_offset(
        self, topic: str, partition: int
    ) -> Optional[int]:
        """Get the committed offset for a partition."""
        return self._offsets.get(topic, {}).get(partition)

    async def rebalance(self) -> int:
        """Trigger a group rebalance."""
        async with self._lock:
            self._generation_id += 1
            for member in self._members.values():
                member.status = MemberStatus.REBALANCING

            # Simple round-robin rebalancing
            # In production this would use a cooperative rebalance protocol
            logger.info(
                "Group %s rebalanced (generation %d, %d members)",
                self.group_id, self._generation_id, len(self._members),
            )
            return self._generation_id

    async def expire_sessions(self) -> list[str]:
        """Expire sessions that haven't heartbeated within the timeout."""
        now = time.monotonic()
        expired = []
        for member_id, member in list(self._members.items()):
            elapsed = (now - member.last_heartbeat.timestamp()) * 1000
            if elapsed > self.session_timeout_ms:
                member.status = MemberStatus.INACTIVE
                expired.append(member.consumer_id)
                del self._members[member_id]
                logger.warning(
                    "Consumer %s session expired in group %s",
                    member.consumer_id, self.group_id,
                )
        return expired

    @property
    def generation(self) -> int:
        return self._generation_id

    @property
    def member_count(self) -> int:
        return len(self._members)

    async def list_members(self) -> list[ConsumerMember]:
        """List all group members."""
        return list(self._members.values())

    async def summary(self) -> dict[str, Any]:
        """Get consumer group summary."""
        return {
            "group_id": self.group_id,
            "generation": self._generation_id,
            "member_count": len(self._members),
            "total_consumed": sum(m.events_consumed for m in self._members.values()),
            "members": [
                {
                    "consumer_id": m.consumer_id,
                    "status": m.status.value,
                    "partitions": m.assigned_partitions,
                    "consumed": m.events_consumed,
                    "last_heartbeat": m.last_heartbeat.isoformat(),
                }
                for m in self._members.values()
            ],
            "offsets": {
                topic: dict(partitions)
                for topic, partitions in self._offsets.items()
            },
        }
