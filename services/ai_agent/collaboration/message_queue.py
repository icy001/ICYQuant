"""Message Queue — asynchronous priority message queue for inter-agent communication.

Pipeline:
    Message (from publisher agent)
        -> MessageQueue.enqueue() (store with priority)
        -> MessageQueue.dequeue() (deliver to subscribers)
        -> MessageQueue.ack() / nack() (confirm delivery)
        -> QueueStats (monitoring)

Provides reliable asynchronous message delivery between agents with
priority support, acknowledgment tracking, and TTL-based expiry.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class QueuePriority(int, Enum):
    """Message priority levels."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class QueueItemStatus(str, Enum):
    """Status of a queue item."""
    PENDING = "pending"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class QueueItem:
    """An item in the message queue.

    Attributes:
        item_id: Unique item identifier.
        topic: Message topic.
        payload: Message payload.
        priority: Message priority.
        sender_id: ID of the sending agent.
        ttl_seconds: Time-to-live in seconds.
        status: Current delivery status.
        enqueued_at: When the item was enqueued.
        retry_count: Number of delivery retries.
    """

    item_id: str = field(default_factory=lambda: uuid4().hex)
    topic: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: QueuePriority = QueuePriority.NORMAL
    sender_id: str = ""
    ttl_seconds: float = 30.0
    status: QueueItemStatus = QueueItemStatus.PENDING
    enqueued_at: float = field(default_factory=time.monotonic)
    retry_count: int = 0

    @property
    def is_expired(self) -> bool:
        """Return whether the item has exceeded its TTL."""
        return (time.monotonic() - self.enqueued_at) > self.ttl_seconds


@dataclass
class QueueStats:
    """Statistics for a message queue.

    Attributes:
        total_enqueued: Total messages enqueued.
        total_dequeued: Total messages dequeued.
        total_acknowledged: Total messages acknowledged.
        total_failed: Total failed deliveries.
        total_expired: Total expired messages.
        current_depth: Current queue depth.
    """

    total_enqueued: int = 0
    total_dequeued: int = 0
    total_acknowledged: int = 0
    total_failed: int = 0
    total_expired: int = 0
    current_depth: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Return stats as a dictionary."""
        return {
            "total_enqueued": self.total_enqueued,
            "total_dequeued": self.total_dequeued,
            "total_acknowledged": self.total_acknowledged,
            "total_failed": self.total_failed,
            "total_expired": self.total_expired,
            "current_depth": self.current_depth,
        }


class MessageQueue:
    """Asynchronous priority message queue for inter-agent communication.

    Provides reliable message delivery with priority support, TTL-based
    expiry, and acknowledgment tracking.

    Supports:
        - Priority-based enqueue/dequeue (CRITICAL → LOW)
        - TTL-based message expiry
        - Acknowledgment (ack/nack) tracking
        - Retry with max attempts
        - Queue statistics
        - Max depth enforcement

    Usage:
        queue = MessageQueue(max_size=10000)
        await queue.initialize()
        item = QueueItem(topic="market.update", payload={...})
        await queue.enqueue(item)
        msg = await queue.dequeue("subscriber_1")
    """

    def __init__(self, max_size: int = 10000) -> None:
        """Initialize the message queue.

        Args:
            max_size: Maximum number of items in the queue.
        """
        self._max_size: int = max_size
        self._queues: Dict[QueuePriority, deque] = {
            p: deque() for p in QueuePriority
        }
        self._pending: Dict[str, QueueItem] = {}  # item_id -> item (awaiting ack)
        self._stats: QueueStats = QueueStats()
        self._initialized: bool = False
        logger.info("MessageQueue created (max_size=%d)", max_size)

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the message queue."""
        if self._initialized:
            logger.warning("MessageQueue already initialized")
            return
        self._initialized = True
        logger.info("MessageQueue initialized")

    async def shutdown(self) -> None:
        """Shut down and clear the queue."""
        if not self._initialized:
            return
        for q in self._queues.values():
            q.clear()
        self._pending.clear()
        self._initialized = False
        logger.info("MessageQueue shutdown complete")

    # ── Enqueue ──

    async def enqueue(self, item: QueueItem) -> bool:
        """Add an item to the queue.

        Args:
            item: The queue item to add.

        Returns:
            True if enqueued successfully, False if queue is full.

        Raises:
            RuntimeError: If the queue is not initialized.
        """
        if not self._initialized:
            raise RuntimeError("MessageQueue not initialized")

        if self.depth >= self._max_size:
            logger.warning("MessageQueue full (depth=%d, max=%d)", self.depth, self._max_size)
            return False

        self._queues[item.priority].append(item)
        self._stats.total_enqueued += 1
        self._stats.current_depth = self.depth
        logger.debug("Message enqueued: %s (topic=%s, priority=%s)",
                     item.item_id, item.topic, item.priority.name)
        return True

    # ── Dequeue ──

    async def dequeue(self, subscriber_id: str) -> Optional[QueueItem]:
        """Dequeue the highest-priority item from the queue.

        Iterates priorities from CRITICAL to LOW, returning the first
        non-expired item.

        Args:
            subscriber_id: ID of the subscribing agent.

        Returns:
            The dequeued item, or None if the queue is empty.
        """
        if not self._initialized:
            raise RuntimeError("MessageQueue not initialized")

        for priority in QueuePriority:
            q = self._queues[priority]
            while q:
                item = q.popleft()

                # Check expiry
                if item.is_expired:
                    self._stats.total_expired += 1
                    logger.debug("Message expired: %s", item.item_id)
                    continue

                # Track as pending
                self._pending[item.item_id] = item
                self._stats.total_dequeued += 1
                self._stats.current_depth = self.depth
                logger.debug("Message dequeued: %s -> %s", item.item_id, subscriber_id)
                return item

        return None

    async def dequeue_batch(
        self, subscriber_id: str, max_items: int = 10,
    ) -> List[QueueItem]:
        """Dequeue multiple items at once.

        Args:
            subscriber_id: ID of the subscribing agent.
            max_items: Maximum items to dequeue.

        Returns:
            List of dequeued items.
        """
        items: List[QueueItem] = []
        for _ in range(max_items):
            item = await self.dequeue(subscriber_id)
            if item is None:
                break
            items.append(item)
        return items

    # ── Acknowledgment ──

    async def ack(self, item_id: str) -> bool:
        """Acknowledge successful delivery of an item.

        Args:
            item_id: The item identifier.

        Returns:
            True if the item was acknowledged.
        """
        if item_id in self._pending:
            del self._pending[item_id]
            self._stats.total_acknowledged += 1
            logger.debug("Message ack: %s", item_id)
            return True
        return False

    async def nack(self, item_id: str, requeue: bool = True) -> bool:
        """Negative-acknowledge (failed) delivery of an item.

        Args:
            item_id: The item identifier.
            requeue: Whether to requeue the item for retry.

        Returns:
            True if the item was found.
        """
        if item_id not in self._pending:
            return False

        item = self._pending.pop(item_id)
        self._stats.total_failed += 1

        if requeue and item.retry_count < 3:
            item.retry_count += 1
            item.enqueued_at = time.monotonic()  # Reset TTL
            await self.enqueue(item)
            logger.debug("Message requeued (retry %d): %s", item.retry_count, item_id)
        else:
            item.status = QueueItemStatus.FAILED
            logger.debug("Message failed (retries exhausted): %s", item_id)

        return True

    # ── Properties ──

    @property
    def depth(self) -> int:
        """Return the current queue depth."""
        return sum(len(q) for q in self._queues.values())

    @property
    def pending_count(self) -> int:
        """Return the number of pending (awaiting ack) items."""
        return len(self._pending)

    @property
    def stats(self) -> QueueStats:
        """Return current queue statistics."""
        self._stats.current_depth = self.depth
        return self._stats

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the queue state.

        Returns:
            Dict with depth, pending count, and statistics.
        """
        return {
            "initialized": self._initialized,
            "depth": self.depth,
            "pending": self.pending_count,
            "max_size": self._max_size,
            "stats": self.stats.to_dict(),
        }
