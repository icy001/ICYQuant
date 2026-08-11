"""
ICYQuant Inference Queue — Priority-based inference request queue.

Manages async inference request queuing with:
  - Priority levels (CRITICAL > HIGH > NORMAL > LOW > BACKGROUND)
  - Bounded queue with backpressure
  - Fair scheduling within priority levels
  - Queue depth monitoring
  - Request timeout while queued
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data
# ---------------------------------------------------------------------------

class Priority(IntEnum):
    """Request priorities (lower = higher priority in heap)."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


@dataclass(order=True)
class QueuedRequest:
    """A request waiting in the inference queue."""
    priority: int
    enqueued_at: float = field(compare=False, default_factory=time.time)
    request_id: str = field(compare=False, default_factory=lambda: str(uuid.uuid4()))
    model_id: str = field(compare=False)
    features: Dict[str, Any] = field(compare=False)
    version: Optional[str] = field(compare=False, default=None)
    timeout_ms: int = field(compare=False, default=5000)
    future: asyncio.Future = field(compare=False, default=None)

    def __post_init__(self):
        if self.future is None:
            self.future = asyncio.get_running_loop().create_future()

    @property
    def wait_time_ms(self) -> float:
        return (time.time() - self.enqueued_at) * 1000

    @property
    def is_expired(self) -> bool:
        return self.wait_time_ms > self.timeout_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id[:8],
            "model_id": self.model_id,
            "priority": Priority(self.priority).name,
            "wait_ms": round(self.wait_time_ms, 2),
        }


@dataclass
class QueueConfig:
    """Queue configuration."""
    max_size: int = 1000
    max_wait_ms: int = 5000
    drain_timeout_seconds: int = 30
    stats_interval: int = 100


# ---------------------------------------------------------------------------
# Inference Queue
# ---------------------------------------------------------------------------

class InferenceQueue:
    """Priority-based inference request queue.

    Usage::

        queue = InferenceQueue()
        await queue.initialize()

        # Producer
        future = await queue.enqueue("nvda_model", features, Priority.HIGH)

        # Consumer (worker)
        async for request in queue.dequeue():
            result = await inference_engine.predict(request.model_id, request.features)
            request.future.set_result(result)
    """

    def __init__(self, config: Optional[QueueConfig] = None):
        self.config = config or QueueConfig()

        # Priority queue (min-heap)
        self._heap: List[Tuple[int, float, int, QueuedRequest]] = []
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
        self._not_full = asyncio.Condition(self._lock)

        # Sequence counter for FIFO ordering within same priority
        self._seq: int = 0

        # Stats
        self._enqueued: int = 0
        self._dequeued: int = 0
        self._rejected: int = 0
        self._timed_out_in_queue: int = 0

        # Shutdown
        self._shutdown = asyncio.Event()
        self._running = False

    async def initialize(self) -> None:
        self._running = True
        logger.info("InferenceQueue initialized — max_size=%d", self.config.max_size)

    async def shutdown(self) -> None:
        """Shutdown the queue."""
        self._running = False
        self._shutdown.set()

        async with self._lock:
            # Fail all pending futures
            for _, _, _, req in self._heap:
                if not req.future.done():
                    req.future.set_exception(
                        RuntimeError("Queue shutting down")
                    )
            self._heap.clear()

        # Notify consumers
        async with self._not_empty:
            self._not_empty.notify_all()

        logger.info("InferenceQueue shutdown — %d requests cancelled",
                    self._enqueued - self._dequeued)

    # ------------------------------------------------------------------
    # Enqueue
    # ------------------------------------------------------------------

    async def enqueue(
        self,
        model_id: str,
        features: Dict[str, Any],
        priority: Priority = Priority.NORMAL,
        *,
        version: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        request_id: Optional[str] = None,
    ) -> asyncio.Future:
        """Enqueue an inference request.

        Args:
            model_id: Model identifier.
            features: Feature dictionary.
            priority: Request priority.
            version: Optional pinned version.
            timeout_ms: Max time to wait in queue.
            request_id: Optional request identifier.

        Returns:
            Future that resolves with the prediction result.
        """
        if not self._running:
            raise RuntimeError("Queue is not running")

        async with self._not_full:
            # Block if queue is full (with backpressure)
            while len(self._heap) >= self.config.max_size:
                await self._not_full.wait()

            request = QueuedRequest(
                priority=int(priority),
                model_id=model_id,
                features=features,
                version=version,
                timeout_ms=timeout_ms or self.config.max_wait_ms,
                request_id=request_id or str(uuid.uuid4()),
            )

            # Push to heap: (priority, enqueue_time, sequence, request)
            self._seq += 1
            heapq.heappush(
                self._heap,
                (request.priority, request.enqueued_at, self._seq, request),
            )
            self._enqueued += 1

        # Notify consumers
        async with self._not_empty:
            self._not_empty.notify()

        return request.future

    async def enqueue_batch(
        self,
        requests: List[Tuple[str, Dict[str, Any]]],
        priority: Priority = Priority.NORMAL,
    ) -> List[asyncio.Future]:
        """Enqueue multiple requests at once."""
        return [
            await self.enqueue(model_id, features, priority=priority)
            for model_id, features in requests
        ]

    # ------------------------------------------------------------------
    # Dequeue
    # ------------------------------------------------------------------

    async def dequeue(self) -> QueuedRequest:
        """Dequeue the highest-priority request.

        Blocks until a request is available or shutdown.
        """
        async with self._not_empty:
            while True:
                if not self._running:
                    raise RuntimeError("Queue is not running")

                if self._heap:
                    # Pop highest priority
                    _, _, _, request = heapq.heappop(self._heap)
                    self._dequeued += 1

                    # Check if request timed out while waiting
                    if request.is_expired:
                        self._timed_out_in_queue += 1
                        if not request.future.done():
                            request.future.set_exception(
                                asyncio.TimeoutError("Request timed out in queue")
                            )
                        # Skip expired requests
                        continue

                    # Notify producers that space is available
                    async with self._not_full:
                        self._not_full.notify()

                    return request

                # Wait for new items
                await self._not_empty.wait()

    async def dequeue_batch(self, max_batch: int = 10) -> List[QueuedRequest]:
        """Dequeue up to max_batch requests."""
        requests: List[QueuedRequest] = []
        for _ in range(max_batch):
            async with self._lock:
                if not self._heap:
                    break
                _, _, _, request = heapq.heappop(self._heap)
                self._dequeued += 1

                if request.is_expired:
                    self._timed_out_in_queue += 1
                    if not request.future.done():
                        request.future.set_exception(
                            asyncio.TimeoutError("Request timed out in queue")
                        )
                    continue

                requests.append(request)

        if requests:
            async with self._not_full:
                self._not_full.notify()

        return requests

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self._heap)

    @property
    def is_empty(self) -> bool:
        return len(self._heap) == 0

    @property
    def is_full(self) -> bool:
        return len(self._heap) >= self.config.max_size

    def get_queue_snapshot(self) -> List[Dict[str, Any]]:
        """Get snapshot of queued requests (sorted by priority)."""
        snapshot = sorted(self._heap, key=lambda x: (x[0], x[1], x[2]))
        return [req.to_dict() for _, _, _, req in snapshot]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "queue_size": self.size,
            "max_size": self.config.max_size,
            "enqueued": self._enqueued,
            "dequeued": self._dequeued,
            "rejected": self._rejected,
            "timed_out_in_queue": self._timed_out_in_queue,
            "utilization": round(self.size / max(self.config.max_size, 1), 4),
        }

    def get_priority_breakdown(self) -> Dict[str, int]:
        """Count of requests by priority level."""
        counts = {"CRITICAL": 0, "HIGH": 0, "NORMAL": 0, "LOW": 0, "BACKGROUND": 0}
        for _, _, _, req in self._heap:
            pri_name = Priority(req.priority).name
            counts[pri_name] = counts.get(pri_name, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        utilization = self.size / max(self.config.max_size, 1)
        status = "healthy"
        if utilization > 0.9:
            status = "degraded"
        if utilization >= 1.0:
            status = "overloaded"

        return {
            "status": status,
            "running": self._running,
            "stats": self.get_stats(),
            "priority_breakdown": self.get_priority_breakdown(),
        }

    def __repr__(self) -> str:
        return f"InferenceQueue(size={self.size}/{self.config.max_size})"
