"""Priority Queue — priority-based, thread-safe queue for fired triggers.

The :class:`PriorityQueue` receives fired trigger items from the evaluation
loop and orders them by priority (Critical > High > Normal > Low), with
FIFO ordering within the same priority level.

Architecture::

    Priority (desc) → FIFO (within level) → Pop → Dispatch
"""

from __future__ import annotations

import heapq
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class Priority:
    """Standard priority levels (lower value = higher priority in min-heap)."""

    CRITICAL = 0
    HIGH = 10
    NORMAL = 50
    LOW = 100


@dataclass(order=True)
class QueueItem:
    """A single item in the priority queue.

    Ordering: priority (asc) → sequence (asc, FIFO for same priority).
    """

    priority: int
    sequence: int
    trigger_id: str = field(compare=False)
    schedule_id: str = field(compare=False)
    payload: Dict[str, Any] = field(default_factory=dict, compare=False)
    fire_at: Optional[datetime] = field(default=None, compare=False)
    enqueued_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc), compare=False
    )


class PriorityQueue:
    """Thread-safe priority queue for fired trigger items.

    Uses a min-heap internally: lower priority numbers = higher urgency.

    Usage::

        q = PriorityQueue(max_size=100_000)
        q.push(trigger_id="t1", schedule_id="s1", priority=Priority.HIGH)
        item = q.pop()
    """

    def __init__(self, max_size: int = 100_000) -> None:
        self._lock = threading.RLock()
        self._max_size = max_size
        self._heap: List[QueueItem] = []
        self._sequence: int = 0

        # Stats
        self._total_pushed: int = 0
        self._total_popped: int = 0
        self._total_dropped: int = 0

    # ------------------------------------------------------------------
    # Push
    # ------------------------------------------------------------------

    def push(
        self,
        trigger_id: str,
        schedule_id: str = "",
        payload: Optional[Dict[str, Any]] = None,
        priority: int = Priority.NORMAL,
        fire_at: Optional[datetime] = None,
    ) -> bool:
        """Push a trigger item into the queue. Returns False if queue is full."""
        with self._lock:
            if len(self._heap) >= self._max_size:
                self._total_dropped += 1
                return False

            self._sequence += 1
            item = QueueItem(
                priority=priority,
                sequence=self._sequence,
                trigger_id=trigger_id,
                schedule_id=schedule_id,
                payload=payload or {},
                fire_at=fire_at,
            )
            heapq.heappush(self._heap, item)
            self._total_pushed += 1
            return True

    def push_batch(self, items: List[QueueItem]) -> int:
        """Push multiple items. Returns count of successfully pushed items."""
        count = 0
        with self._lock:
            for item in items:
                if len(self._heap) >= self._max_size:
                    self._total_dropped += 1
                    continue
                self._sequence += 1
                item.sequence = self._sequence
                heapq.heappush(self._heap, item)
                count += 1
            self._total_pushed += count
        return count

    # ------------------------------------------------------------------
    # Pop
    # ------------------------------------------------------------------

    def pop(self) -> Optional[QueueItem]:
        """Pop the highest-priority item. Returns None if empty."""
        with self._lock:
            if not self._heap:
                return None
            item = heapq.heappop(self._heap)
            self._total_popped += 1
            return item

    def peek(self) -> Optional[QueueItem]:
        """Return the highest-priority item without removing it."""
        with self._lock:
            return self._heap[0] if self._heap else None

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        with self._lock:
            return len(self._heap)

    def is_empty(self) -> bool:
        return len(self) == 0

    def is_full(self) -> bool:
        return len(self) >= self._max_size

    def clear(self) -> None:
        with self._lock:
            self._heap.clear()

    def get_priority_distribution(self) -> Dict[str, int]:
        """Return count of items per priority level."""
        dist: Dict[str, int] = {"critical": 0, "high": 0, "normal": 0, "low": 0}
        with self._lock:
            for item in self._heap:
                if item.priority <= Priority.CRITICAL:
                    dist["critical"] += 1
                elif item.priority <= Priority.HIGH:
                    dist["high"] += 1
                elif item.priority <= Priority.NORMAL:
                    dist["normal"] += 1
                else:
                    dist["low"] += 1
        return dist

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "size": len(self._heap),
                "max_size": self._max_size,
                "utilization_pct": (
                    len(self._heap) / max(self._max_size, 1) * 100
                ),
                "total_pushed": self._total_pushed,
                "total_popped": self._total_popped,
                "total_dropped": self._total_dropped,
                "distribution": self.get_priority_distribution(),
            }
