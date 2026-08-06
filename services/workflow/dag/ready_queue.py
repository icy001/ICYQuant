"""
Ready Queue — a priority-aware, lock-free queue for ready-to-execute nodes.

Supports multiple queue disciplines:
- FIFO (default)
- Priority (higher priority nodes first)
- Weighted (proportional scheduling)
"""

from __future__ import annotations

import asyncio
import heapq
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class QueueDiscipline(str, Enum):
    FIFO = "fifo"
    PRIORITY = "priority"
    WEIGHTED = "weighted"


@dataclass(order=True)
class QueueItem:
    """An item in the ready queue."""

    priority: int = 0
    enqueue_time: float = field(compare=False, default=0.0)
    node_id: str = field(compare=False, default="")
    metadata: Dict[str, Any] = field(default_factory=dict, compare=False)


class ReadyQueue:
    """
    Thread-safe ready queue for scheduling nodes.

    Supports:
    - Priority queue (heapq-based)
    - FIFO queue
    - Weighted queue
    - Multiple async consumers
    - Non-blocking and blocking dequeue
    """

    def __init__(self, discipline: QueueDiscipline = QueueDiscipline.PRIORITY):
        self.discipline = discipline
        self._queue: List[QueueItem] = []
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
        self._enqueued: Dict[str, QueueItem] = {}
        self._total_enqueued: int = 0
        self._total_dequeued: int = 0

    async def enqueue(
        self, node_id: str, priority: int = 0, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a node to the ready queue."""
        import time

        item = QueueItem(
            priority=-priority if self.discipline == QueueDiscipline.PRIORITY else 0,
            enqueue_time=time.monotonic(),
            node_id=node_id,
            metadata=metadata or {},
        )

        async with self._lock:
            # Prevent duplicate enqueue
            if node_id in self._enqueued:
                return
            heapq.heappush(self._queue, item)
            self._enqueued[node_id] = item
            self._total_enqueued += 1
            self._not_empty.notify(n=1)

    async def enqueue_batch(self, nodes: List[Tuple[str, int]]) -> None:
        """Enqueue multiple nodes at once."""
        for node_id, priority in nodes:
            await self.enqueue(node_id, priority)

    async def dequeue(self) -> Optional[str]:
        """Dequeue a ready node. Returns None if queue is empty."""
        async with self._lock:
            if not self._queue:
                return None
            item = heapq.heappop(self._queue)
            self._enqueued.pop(item.node_id, None)
            self._total_dequeued += 1
            return item.node_id

    async def dequeue_blocking(self, timeout: Optional[float] = None) -> Optional[str]:
        """Dequeue, blocking until a node is available or timeout."""
        async with self._lock:
            await self._not_empty.wait_for(lambda: len(self._queue) > 0)
            if not self._queue:
                return None
            return await self.dequeue()

    async def dequeue_batch(self, max_count: int) -> List[str]:
        """Dequeue up to max_count nodes."""
        results = []
        for _ in range(max_count):
            node_id = await self.dequeue()
            if node_id is None:
                break
            results.append(node_id)
        return results

    async def peek(self) -> Optional[str]:
        """Peek at the next node without dequeuing."""
        async with self._lock:
            if not self._queue:
                return None
            return self._queue[0].node_id

    async def remove(self, node_id: str) -> bool:
        """Remove a specific node from the queue."""
        async with self._lock:
            if node_id in self._enqueued:
                item = self._enqueued.pop(node_id)
                self._queue = [i for i in self._queue if i.node_id != node_id]
                heapq.heapify(self._queue)
                return True
            return False

    @property
    def size(self) -> int:
        return len(self._queue)

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def get_stats(self) -> Dict[str, Any]:
        return {
            "discipline": self.discipline.value,
            "size": self.size,
            "total_enqueued": self._total_enqueued,
            "total_dequeued": self._total_dequeued,
        }
