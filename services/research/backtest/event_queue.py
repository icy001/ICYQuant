"""Event Queue — thread-safe priority event queue for the backtesting engine.

Supports priority-based event ordering within timestamps, ensuring
proper event dispatch order in the event-driven architecture.
"""

from __future__ import annotations

import asyncio
import heapq
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class EventPriority(int, Enum):
    """Event priority levels (lower = higher priority within same timestamp)."""

    CRITICAL = 0  # system/crash events
    HIGH = 10  # corporate actions, dividends
    MEDIUM = 50  # market data, signals
    LOW = 100  # settlements, reports
    IDLE = 200  # housekeeping


@dataclass(order=True)
class _QueueItem:
    """Internal queue item with ordering key."""

    timestamp_epoch: float
    priority: int
    sequence: int
    event: "BacktestEvent" = field(compare=False)


@dataclass
class BacktestEvent:
    """A backtesting event in the event-driven architecture.

    Events flow::

        Market → Signal → Order → Trade → Position → Settlement
    """

    event_type: str
    timestamp: str = field(default_factory=lambda: str(uuid4()))
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = "system"
    event_id: str = field(default_factory=lambda: str(uuid4()))
    priority: EventPriority = EventPriority.MEDIUM

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "source": self.source,
            "priority": self.priority.value,
            "data": self.data,
            "metadata": self.metadata,
        }


class EventQueue:
    """Thread-safe priority event queue.

    Events are ordered by:
    1. Timestamp (epoch seconds)
    2. Priority (lower = sooner)
    3. Insertion sequence (FIFO within same timestamp+priority)

    Supports both synchronous and asynchronous access.
    """

    def __init__(self, max_size: int = 100000) -> None:
        self._heap: List[_QueueItem] = []
        self._lock = asyncio.Lock()
        self._sequence = 0
        self._max_size = max_size
        self._push_count = 0
        self._pop_count = 0
        self._peak_size = 0

    # ── push ───────────────────────────────────────────────────────────────

    async def push(self, event: BacktestEvent, timestamp_epoch: Optional[float] = None) -> bool:
        """Push an event onto the queue.

        Args:
            event: The backtest event.
            timestamp_epoch: Optional epoch timestamp for ordering.
                             Defaults to 0 (immediate).

        Returns:
            True if pushed, False if queue is full.
        """
        async with self._lock:
            if len(self._heap) >= self._max_size:
                logger.warning("Event queue full (%d), dropping event: %s", self._max_size, event.event_id[:8])
                return False

            ts = timestamp_epoch if timestamp_epoch is not None else 0.0
            item = _QueueItem(
                timestamp_epoch=ts,
                priority=event.priority.value,
                sequence=self._sequence,
                event=event,
            )
            self._sequence += 1
            heapq.heappush(self._heap, item)
            self._push_count += 1
            self._peak_size = max(self._peak_size, len(self._heap))
            return True

    async def push_batch(
        self,
        events: List[BacktestEvent],
        timestamp_epoch: Optional[float] = None,
    ) -> int:
        """Push multiple events at the same timestamp."""
        pushed = 0
        for event in events:
            if await self.push(event, timestamp_epoch):
                pushed += 1
        return pushed

    # ── pop ────────────────────────────────────────────────────────────────

    async def pop(self) -> Optional[BacktestEvent]:
        """Pop the next event from the queue (returns None if empty)."""
        async with self._lock:
            if not self._heap:
                return None
            item = heapq.heappop(self._heap)
            self._pop_count += 1
            return item.event

    async def pop_many(self, n: int = 100) -> List[BacktestEvent]:
        """Pop up to n events from the queue."""
        events: List[BacktestEvent] = []
        async with self._lock:
            for _ in range(min(n, len(self._heap))):
                item = heapq.heappop(self._heap)
                self._pop_count += 1
                events.append(item.event)
        return events

    # ── peek ───────────────────────────────────────────────────────────────

    async def peek(self) -> Optional[BacktestEvent]:
        """Peek at the next event without removing it."""
        async with self._lock:
            if not self._heap:
                return None
            return self._heap[0].event

    async def peek_all(self) -> List[BacktestEvent]:
        """Return all events in queue order without removing them."""
        async with self._lock:
            sorted_items = sorted(self._heap)
            return [item.event for item in sorted_items]

    # ── query ──────────────────────────────────────────────────────────────

    async def size(self) -> int:
        """Get current queue size."""
        async with self._lock:
            return len(self._heap)

    async def is_empty(self) -> bool:
        return await self.size() == 0

    async def clear(self) -> None:
        """Clear all events from the queue."""
        async with self._lock:
            self._heap.clear()
            logger.info("Event queue cleared")

    async def stats(self) -> Dict[str, Any]:
        """Return queue statistics."""
        async with self._lock:
            return {
                "current_size": len(self._heap),
                "max_size": self._max_size,
                "peak_size": self._peak_size,
                "push_count": self._push_count,
                "pop_count": self._pop_count,
                "sequence": self._sequence,
            }

    # ── filter ─────────────────────────────────────────────────────────────

    async def filter_by_type(self, event_type: str) -> List[BacktestEvent]:
        """Get all events of a specific type (does not remove)."""
        async with self._lock:
            return [
                item.event for item in self._heap
                if item.event.event_type == event_type
            ]

    async def remove_by_type(self, event_type: str) -> int:
        """Remove all events of a specific type."""
        async with self._lock:
            before = len(self._heap)
            self._heap = [
                item for item in self._heap
                if item.event.event_type != event_type
            ]
            heapq.heapify(self._heap)
            removed = before - len(self._heap)
            if removed > 0:
                logger.debug("Removed %d events of type: %s", removed, event_type)
            return removed
