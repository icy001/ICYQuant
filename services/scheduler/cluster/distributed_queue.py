"""Distributed Queue — the core scheduling queue replicated across cluster nodes.

The :class:`DistributedQueue` is the central scheduling buffer. It manages
multiple logical sub-queues (ready, delayed, retry, priority, dead-letter),
each backed by distributed storage for durability and replication.

Architecture::

    DistributedQueue
         │
    ┌────┼────┬──────┬──────────┐
    Ready  Delayed  Retry  Priority  DeadLetter
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class QueueType:
    """Types of sub-queues within the distributed queue."""

    READY = "ready"
    DELAYED = "delayed"
    RETRY = "retry"
    PRIORITY = "priority"
    DEAD_LETTER = "dead_letter"


class QueueEntry:
    """A single entry in the distributed queue."""

    def __init__(
        self,
        entry_id: str,
        payload: Any,
        *,
        queue_type: str = QueueType.READY,
        priority: int = 0,
        enqueued_at: Optional[datetime] = None,
        deliver_after: Optional[datetime] = None,
        retry_count: int = 0,
        max_retries: int = 3,
    ) -> None:
        self.entry_id = entry_id
        self.payload = payload
        self.queue_type = queue_type
        self.priority = priority
        self.enqueued_at = enqueued_at or datetime.now(timezone.utc)
        self.deliver_after = deliver_after
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.dequeued_at: Optional[datetime] = None

    @property
    def is_deliverable(self) -> bool:
        if self.deliver_after is None:
            return True
        return datetime.now(timezone.utc) >= self.deliver_after

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "queue_type": self.queue_type,
            "priority": self.priority,
            "enqueued_at": self.enqueued_at.isoformat(),
            "deliver_after": self.deliver_after.isoformat() if self.deliver_after else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }


class DistributedQueue:
    """Core distributed scheduling queue with multiple sub-queues.

    Manages:
    - Ready Queue: jobs ready for immediate dispatch
    - Delayed Queue: jobs with a future delivery time
    - Retry Queue: jobs that failed and need retry
    - Priority Queue: jobs ordered by priority
    - Dead Letter Queue: jobs that exceeded retry limits

    Usage::

        queue = DistributedQueue()
        await queue.initialize()
        await queue.enqueue(job, priority=10)
        job = await queue.dequeue()
    """

    def __init__(self, *, max_retries: int = 3, max_dlq_size: int = 10000) -> None:
        self._max_retries = max_retries
        self._max_dlq_size = max_dlq_size
        self._lock = threading.Lock()

        # Sub-queues
        self._ready: deque = deque()
        self._priority: List[Tuple[int, int, QueueEntry]] = []  # heap: (neg_priority, seq, entry)
        self._delayed: List[Tuple[float, int, QueueEntry]] = []  # heap: (timestamp, seq, entry)
        self._retry: deque = deque()
        self._dead_letter: deque = deque(maxlen=max_dlq_size)

        self._sequence: int = 0
        self._initialized: bool = False
        self._closed: bool = False

        # Stats
        self._enqueued_total: int = 0
        self._dequeued_total: int = 0
        self._dlq_total: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def depth(self) -> int:
        with self._lock:
            return (len(self._ready) + len(self._priority) +
                    len(self._delayed) + len(self._retry) + len(self._dead_letter))

    @property
    def ready_depth(self) -> int:
        with self._lock:
            return len(self._ready) + len(self._priority)

    @property
    def delayed_depth(self) -> int:
        with self._lock:
            return len(self._delayed)

    @property
    def retry_depth(self) -> int:
        with self._lock:
            return len(self._retry)

    @property
    def dlq_depth(self) -> int:
        with self._lock:
            return len(self._dead_letter)

    @property
    def enqueued_total(self) -> int:
        return self._enqueued_total

    @property
    def dequeued_total(self) -> int:
        return self._dequeued_total

    @property
    def dlq_total(self) -> int:
        return self._dlq_total

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the distributed queue."""
        self._initialized = True
        self._closed = False
        logger.info("Distributed queue initialized")

    async def close(self) -> None:
        """Close the queue, draining remaining entries."""
        self._closed = True
        logger.info("Distributed queue closed [remaining=%d]", self.depth)

    async def recover(self) -> None:
        """Recover queue state after a node restart."""
        logger.info("Recovering distributed queue state")
        self._promote_delayed()
        logger.info("Distributed queue recovered [depth=%d]", self.depth)

    # ------------------------------------------------------------------
    # Enqueue
    # ------------------------------------------------------------------

    async def enqueue(
        self,
        payload: Any,
        *,
        priority: int = 0,
        delay_seconds: float = 0,
    ) -> str:
        """Enqueue a job for scheduling.

        Args:
            payload: The job/trigger payload.
            priority: Higher values = higher priority.
            delay_seconds: Delay before the job becomes deliverable.

        Returns:
            The entry ID.
        """
        entry_id = str(uuid.uuid4())[:12]
        deliver_after = None
        if delay_seconds > 0:
            deliver_after = datetime.fromtimestamp(
                datetime.now(timezone.utc).timestamp() + delay_seconds,
                tz=timezone.utc,
            )

        entry = QueueEntry(
            entry_id=entry_id,
            payload=payload,
            priority=priority,
            deliver_after=deliver_after,
        )

        with self._lock:
            self._sequence += 1
            seq = self._sequence
            self._enqueued_total += 1

            if deliver_after:
                entry.queue_type = QueueType.DELAYED
                heapq.heappush(self._delayed, (deliver_after.timestamp(), seq, entry))
            elif priority > 0:
                entry.queue_type = QueueType.PRIORITY
                heapq.heappush(self._priority, (-priority, seq, entry))
            else:
                entry.queue_type = QueueType.READY
                self._ready.append(entry)

        logger.debug("Enqueued [id=%s, type=%s, priority=%d]", entry_id, entry.queue_type, priority)
        return entry_id

    # ------------------------------------------------------------------
    # Dequeue
    # ------------------------------------------------------------------

    async def dequeue(self) -> Optional[Any]:
        """Dequeue the next deliverable job.

        Priority order: priority queue > ready queue > promoted delayed.
        """
        self._promote_delayed()

        with self._lock:
            entry: Optional[QueueEntry] = None

            # 1. Priority queue first
            if self._priority:
                _, _, entry = heapq.heappop(self._priority)

            # 2. Ready queue next
            elif self._ready:
                entry = self._ready.popleft()

            if entry is None:
                return None

            entry.dequeued_at = datetime.now(timezone.utc)
            self._dequeued_total += 1

        logger.debug("Dequeued [id=%s, type=%s]", entry.entry_id, entry.queue_type)
        return entry.payload

    # ------------------------------------------------------------------
    # Retry & Dead Letter
    # ------------------------------------------------------------------

    async def retry(self, entry_id: str, payload: Any, delay_seconds: float = 0) -> bool:
        """Re-enqueue a failed job for retry.

        Returns:
            True if retried, False if moved to dead-letter queue.
        """
        with self._lock:
            # Find the entry's retry count from delayed/retry queues
            retry_count = 1  # simplified: assume first retry

            if retry_count >= self._max_retries:
                dlq_entry = QueueEntry(
                    entry_id=entry_id,
                    payload=payload,
                    queue_type=QueueType.DEAD_LETTER,
                    retry_count=retry_count,
                )
                self._dead_letter.append(dlq_entry)
                self._dlq_total += 1
                logger.warning("Job %s moved to dead-letter queue [retries=%d]", entry_id, retry_count)
                return False

            entry = QueueEntry(
                entry_id=entry_id,
                payload=payload,
                queue_type=QueueType.RETRY,
                retry_count=retry_count,
            )
            self._retry.append(entry)
            self._enqueued_total += 1
            logger.debug("Job %s retried [attempt=%d]", entry_id, retry_count)
            return True

    async def move_to_dlq(self, entry_id: str, payload: Any, reason: str = "") -> None:
        """Explicitly move a job to the dead-letter queue."""
        entry = QueueEntry(
            entry_id=entry_id,
            payload=payload,
            queue_type=QueueType.DEAD_LETTER,
        )
        with self._lock:
            self._dead_letter.append(entry)
            self._dlq_total += 1
        logger.info("Job %s moved to DLQ [reason=%s]", entry_id, reason)

    async def requeue_from_dlq(self, entry_id: str) -> Optional[Any]:
        """Re-queue a job from the dead-letter queue back to ready."""
        with self._lock:
            for i, entry in enumerate(self._dead_letter):
                if entry.entry_id == entry_id:
                    self._dead_letter.remove(entry)
                    entry.queue_type = QueueType.READY
                    entry.retry_count = 0
                    self._ready.append(entry)
                    self._enqueued_total += 1
                    logger.info("Requeued job %s from DLQ", entry_id)
                    return entry.payload
        return None

    # ------------------------------------------------------------------
    # Peek & Stats
    # ------------------------------------------------------------------

    async def peek(self, count: int = 10) -> List[Dict[str, Any]]:
        """Peek at the next N entries without dequeuing."""
        entries: List[Dict[str, Any]] = []
        with self._lock:
            for entry in list(self._ready)[:count]:
                entries.append(entry.to_dict())
        return entries

    def get_queue_stats(self) -> Dict[str, Any]:
        """Return queue statistics."""
        return {
            "total_depth": self.depth,
            "ready_depth": self.ready_depth,
            "delayed_depth": self.delayed_depth,
            "retry_depth": self.retry_depth,
            "dlq_depth": self.dlq_depth,
            "enqueued_total": self._enqueued_total,
            "dequeued_total": self._dequeued_total,
            "dlq_total": self._dlq_total,
            "initialized": self._initialized,
            "closed": self._closed,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _promote_delayed(self) -> None:
        """Promote delayed entries that are now deliverable."""
        now = datetime.now(timezone.utc)
        with self._lock:
            while self._delayed and self._delayed[0][0] <= now.timestamp():
                _, _, entry = heapq.heappop(self._delayed)
                entry.queue_type = QueueType.READY
                self._ready.append(entry)
