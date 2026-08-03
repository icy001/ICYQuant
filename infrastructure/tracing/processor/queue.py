"""Span queue management."""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional


class SpanQueue:
    """
    Span queue with overflow protection.

    Provides a FIFO queue for spans with
    configurable overflow protection and
    backpressure support.

    Usage:
        queue = SpanQueue(max_size=2048)
        queue.put(span)
        batch = queue.get_batch(512)
    """

    def __init__(
        self,
        max_size: int = 2048,
    ) -> None:
        self._max_size = max_size
        self._items: List[Any] = []
        self._overflow_count: int = 0
        self._total_enqueued: int = 0
        self._total_dequeued: int = 0

    @property
    def size(self) -> int:
        return len(self._items)

    @property
    def is_full(self) -> bool:
        return len(self._items) >= self._max_size

    @property
    def overflow_count(self) -> int:
        return self._overflow_count

    def put(self, span: Any) -> bool:
        """Add a span to the queue. Returns False if dropped."""
        if self.is_full:
            self._overflow_count += 1
            return False
        self._items.append(span)
        self._total_enqueued += 1
        return True

    def get_batch(self, batch_size: int = 512) -> List[Any]:
        """Get a batch of spans from the queue."""
        batch = self._items[:batch_size]
        self._items = self._items[batch_size:]
        self._total_dequeued += len(batch)
        return batch

    def drain(self) -> List[Any]:
        """Drain all spans from the queue."""
        items = self._items
        self._items = []
        self._total_dequeued += len(items)
        return items

    def clear(self) -> None:
        """Clear the queue."""
        self._items.clear()

    def get_stats(self) -> dict:
        return {
            "size": self.size,
            "max_size": self._max_size,
            "overflow": self._overflow_count,
            "total_enqueued": self._total_enqueued,
            "total_dequeued": self._total_dequeued,
        }
