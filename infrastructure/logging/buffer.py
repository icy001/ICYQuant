"""
Memory buffer for log records.

Provides an in-memory ring buffer for
buffering log records when downstream
handlers are slow or unavailable.

Supports multiple eviction strategies:
- FIFO: First-in, first-out
- Ring Buffer: Overwrite oldest when full
- Drop Oldest: Remove oldest to make space
- Drop Newest: Reject new records when full
"""

from __future__ import annotations

from collections import deque
from typing import List, Optional

from .models import LogEntry


class MemoryBuffer:
    """
    In-memory log buffer.

    Buffers log records in memory when
    downstream handlers are slow or
    unavailable, preventing data loss
    during transient failures.

    Eviction strategies:
    - FIFO: Standard queue (deque with maxlen)
    - Ring Buffer: Overwrite oldest
    - Drop Oldest: Remove oldest before adding
    - Drop Newest: Reject when full

    Usage:
        buffer = MemoryBuffer(
            capacity=50000,
            strategy="ring",
        )
        buffer.add(log_entry)
        records = buffer.drain(100)
    """

    def __init__(
        self,
        capacity: int = 50000,
        strategy: str = "ring",
    ) -> None:
        """
        Initialize memory buffer.

        Args:
            capacity: Maximum buffer capacity.
            strategy: Eviction strategy (fifo, ring, drop_oldest, drop_newest).
        """

        self._capacity = capacity
        self._strategy = strategy
        self._buffer: deque = deque(maxlen=capacity)
        self._total_added: int = 0
        self._total_drained: int = 0
        self._total_dropped: int = 0

    @property
    def capacity(
        self,
    ) -> int:
        """Get buffer capacity."""
        return self._capacity

    @property
    def strategy(
        self,
    ) -> str:
        """Get eviction strategy."""
        return self._strategy

    @property
    def size(
        self,
    ) -> int:
        """Get current buffer size."""
        return len(self._buffer)

    @property
    def is_full(
        self,
    ) -> bool:
        """Check if buffer is full."""
        return len(self._buffer) >= self._capacity

    @property
    def is_empty(
        self,
    ) -> bool:
        """Check if buffer is empty."""
        return len(self._buffer) == 0

    @property
    def total_added(
        self,
    ) -> int:
        """Get total records added."""
        return self._total_added

    @property
    def total_drained(
        self,
    ) -> int:
        """Get total records drained."""
        return self._total_drained

    @property
    def total_dropped(
        self,
    ) -> int:
        """Get total records dropped."""
        return self._total_dropped

    def add(
        self,
        record: LogEntry,
    ) -> bool:
        """
        Add a record to the buffer.

        Args:
            record: LogEntry to add.

        Returns:
            True if accepted, False if dropped.
        """

        self._total_added += 1

        if self._strategy in ("fifo", "ring"):
            # deque with maxlen handles this automatically
            if len(self._buffer) == self._capacity:
                self._total_dropped += 1
            self._buffer.append(record)
            return True

        if self._strategy == "drop_oldest":
            if len(self._buffer) >= self._capacity:
                self._buffer.popleft()
                self._total_dropped += 1
            self._buffer.append(record)
            return True

        if self._strategy == "drop_newest":
            if len(self._buffer) >= self._capacity:
                self._total_dropped += 1
                return False
            self._buffer.append(record)
            return True

        # Default: append
        self._buffer.append(record)
        return True

    def drain(
        self,
        count: int = 0,
    ) -> List[LogEntry]:
        """
        Drain records from the buffer.

        Args:
            count: Maximum records to drain (0 = all).

        Returns:
            List of drained records.
        """

        if count <= 0 or count > len(self._buffer):
            count = len(self._buffer)

        records = []
        for _ in range(count):
            if self._buffer:
                records.append(self._buffer.popleft())

        self._total_drained += len(records)
        return records

    def peek(
        self,
        count: int = 1,
    ) -> List[LogEntry]:
        """
        Peek at records without removing.

        Args:
            count: Number of records to peek.

        Returns:
            List of peeked records.
        """

        count = min(count, len(self._buffer))
        return list(self._buffer)[:count]

    def clear(
        self,
    ) -> int:
        """
        Clear the buffer.

        Returns:
            Number of records cleared.
        """

        count = len(self._buffer)
        self._buffer.clear()
        return count

    def get_stats(
        self,
    ) -> dict:
        """
        Get buffer statistics.

        Returns:
            Statistics dictionary.
        """

        return {
            "size": len(self._buffer),
            "capacity": self._capacity,
            "strategy": self._strategy,
            "total_added": self._total_added,
            "total_drained": self._total_drained,
            "total_dropped": self._total_dropped,
        }
