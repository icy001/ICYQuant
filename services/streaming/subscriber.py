"""
Subscriber — event subscription with consumer groups, offset management,
and multiple subscription modes.

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


class SubscriptionMode(str, Enum):
    EARLIEST = "earliest"
    LATEST = "latest"
    AT_OFFSET = "at_offset"
    AT_TIMESTAMP = "at_timestamp"


@dataclass
class Subscription:
    """A subscription to a topic."""
    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    group_id: str = ""
    mode: SubscriptionMode = SubscriptionMode.LATEST
    handler: Any = None
    current_offset: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    paused: bool = False
    events_processed: int = 0
    events_errored: int = 0
    last_event_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Subscriber:
    """
    Event subscriber with consumer group support and offset management.

    Features:
    - Multiple subscription modes (earliest, latest, at_offset, at_timestamp)
    - Consumer group coordination
    - Automatic offset commit
    - Pause/resume subscriptions
    - Per-subscription statistics

    Usage::

        subscriber = Subscriber(metrics)
        sub_id = await subscriber.subscribe("market.tick", handle_tick, group_id="algo-1")
        await subscriber.pause(sub_id)
        await subscriber.unsubscribe(sub_id)
    """

    def __init__(self, metrics: Any = None) -> None:
        self.metrics = metrics
        self._subscriptions: dict[str, Subscription] = {}
        self._topic_subscribers: dict[str, set[str]] = {}
        self._group_members: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(
        self,
        topic: str,
        handler: Any,
        *,
        group_id: str = "default",
        mode: str = "latest",
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Subscribe to a topic with a handler function."""
        async with self._lock:
            sub = Subscription(
                topic=topic,
                group_id=group_id,
                mode=SubscriptionMode(mode),
                handler=handler,
                metadata=metadata or {},
            )

            self._subscriptions[sub.subscription_id] = sub

            # Track by topic
            if topic not in self._topic_subscribers:
                self._topic_subscribers[topic] = set()
            self._topic_subscribers[topic].add(sub.subscription_id)

            # Track by group
            if group_id not in self._group_members:
                self._group_members[group_id] = set()
            self._group_members[group_id].add(sub.subscription_id)

            logger.info(
                "Subscribed: %s → %s (group=%s, mode=%s)",
                sub.subscription_id[:8], topic, group_id, mode,
            )
            return sub.subscription_id

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from a topic."""
        async with self._lock:
            sub = self._subscriptions.pop(subscription_id, None)
            if sub is None:
                return False

            self._topic_subscribers.get(sub.topic, set()).discard(subscription_id)
            self._group_members.get(sub.group_id, set()).discard(subscription_id)

            logger.info("Unsubscribed: %s", subscription_id[:8])
            return True

    async def pause(self, subscription_id: str) -> bool:
        """Pause a subscription."""
        sub = self._subscriptions.get(subscription_id)
        if sub:
            sub.paused = True
            return True
        return False

    async def resume(self, subscription_id: str) -> bool:
        """Resume a paused subscription."""
        sub = self._subscriptions.get(subscription_id)
        if sub:
            sub.paused = False
            return True
        return False

    async def commit_offset(self, subscription_id: str, offset: int) -> bool:
        """Commit a consumer offset."""
        sub = self._subscriptions.get(subscription_id)
        if sub:
            sub.current_offset = offset
            return True
        return False

    async def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """Get a subscription by ID."""
        return self._subscriptions.get(subscription_id)

    async def get_topic_subscribers(self, topic: str) -> list[Subscription]:
        """Get all subscribers for a topic."""
        sub_ids = self._topic_subscribers.get(topic, set())
        return [self._subscriptions[sid] for sid in sub_ids if sid in self._subscriptions]

    async def get_group_members(self, group_id: str) -> list[Subscription]:
        """Get all members of a consumer group."""
        member_ids = self._group_members.get(group_id, set())
        return [self._subscriptions[mid] for mid in member_ids if mid in self._subscriptions]

    async def active_count(self) -> int:
        """Count active (non-paused) subscriptions."""
        return sum(1 for s in self._subscriptions.values() if not s.paused)

    async def record_processed(self, subscription_id: str, success: bool = True) -> None:
        """Record a processed event for a subscription."""
        sub = self._subscriptions.get(subscription_id)
        if sub:
            sub.last_event_at = datetime.now(timezone.utc)
            if success:
                sub.events_processed += 1
            else:
                sub.events_errored += 1

    async def list_all(self) -> list[Subscription]:
        """List all subscriptions."""
        return list(self._subscriptions.values())

    async def stats(self) -> dict[str, Any]:
        """Get subscriber statistics."""
        total_processed = sum(s.events_processed for s in self._subscriptions.values())
        total_errored = sum(s.events_errored for s in self._subscriptions.values())

        return {
            "total_subscriptions": len(self._subscriptions),
            "active_subscriptions": await self.active_count(),
            "total_topics": len(self._topic_subscribers),
            "total_groups": len(self._group_members),
            "total_processed": total_processed,
            "total_errored": total_errored,
            "topics": {
                topic: len(subs)
                for topic, subs in self._topic_subscribers.items()
            },
            "groups": {
                group: len(members)
                for group, members in self._group_members.items()
            },
        }
