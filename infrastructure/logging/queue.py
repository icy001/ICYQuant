"""
Async logging queue.

Provides an asyncio.Queue-based log
queue that decouples log production from
log consumption, enabling high-throughput
non-blocking logging.

The queue supports configurable capacity
and backpressure policies for graceful
degradation under load.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from .models import LogEntry
from .policy import BackpressurePolicy


class LogQueue:
    """
    Async logging queue.

    Wraps asyncio.Queue with configurable
    capacity and backpressure policy. When
    the queue is full, the policy determines
    whether to block, drop, or buffer.

    Usage:
        queue = LogQueue(max_size=10000)
        await queue.put(log_entry)
        record = await queue.get()
    """

    def __init__(
        self,
        max_size: int = 10000,
        policy: BackpressurePolicy = BackpressurePolicy.BLOCK,
    ) -> None:
        """
        Initialize log queue.

        Args:
            max_size: Maximum queue capacity.
            policy: Backpressure policy when full.
        """

        self._max_size = max_size
        self._policy = policy
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._dropped_count: int = 0
        self._total_put: int = 0
        self._total_get: int = 0

    @property
    def max_size(
        self,
    ) -> int:
        """Get max queue size."""
        return self._max_size

    @property
    def policy(
        self,
    ) -> BackpressurePolicy:
        """Get backpressure policy."""
        return self._policy

    @property
    def dropped_count(
        self,
    ) -> int:
        """Get total dropped records."""
        return self._dropped_count

    async def put(
        self,
        record: LogEntry,
    ) -> bool:
        """
        Put a record into the queue.

        Behavior depends on backpressure policy:
        - BLOCK: Await until space is available.
        - DROP_NEWEST: Drop the record if full.
        - DROP_OLDEST: Remove oldest to make space.

        Args:
            record: LogEntry to queue.

        Returns:
            True if accepted, False if dropped.
        """

        self._total_put += 1

        if self._policy == BackpressurePolicy.BLOCK:
            await self._queue.put(record)
            return True

        if self._queue.full():
            if self._policy == BackpressurePolicy.DROP_NEWEST:
                self._dropped_count += 1
                return False
            elif self._policy == BackpressurePolicy.DROP_OLDEST:
                try:
                    self._queue.get_nowait()
                    self._dropped_count += 1
                except asyncio.QueueEmpty:
                    pass
                await self._queue.put(record)
                return True

        await self._queue.put(record)
        return True

    def put_nowait(
        self,
        record: LogEntry,
    ) -> bool:
        """
        Non-async put attempt.

        Args:
            record: LogEntry to queue.

        Returns:
            True if accepted, False if dropped/failed.
        """

        self._total_put += 1

        try:
            if self._queue.full():
                if self._policy == BackpressurePolicy.DROP_NEWEST:
                    self._dropped_count += 1
                    return False
                elif self._policy == BackpressurePolicy.DROP_OLDEST:
                    self._queue.get_nowait()
                    self._dropped_count += 1

            self._queue.put_nowait(record)
            return True
        except asyncio.QueueFull:
            self._dropped_count += 1
            return False

    async def get(
        self,
    ) -> LogEntry:
        """
        Get a record from the queue.

        Returns:
            Next LogEntry in the queue.
        """

        record = await self._queue.get()
        self._total_get += 1
        return record

    def get_nowait(
        self,
    ) -> Optional[LogEntry]:
        """
        Non-async get attempt.

        Returns:
            LogEntry or None if empty.
        """

        try:
            record = self._queue.get_nowait()
            self._total_get += 1
            return record
        except asyncio.QueueEmpty:
            return None

    def size(
        self,
    ) -> int:
        """Get current queue size."""
        return self._queue.qsize()

    def is_full(
        self,
    ) -> bool:
        """Check if queue is full."""
        return self._queue.full()

    def is_empty(
        self,
    ) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()

    def get_stats(
        self,
    ) -> dict:
        """
        Get queue statistics.

        Returns:
            Statistics dictionary.
        """

        return {
            "size": self.size(),
            "max_size": self._max_size,
            "policy": self._policy.value,
            "total_put": self._total_put,
            "total_get": self._total_get,
            "dropped": self._dropped_count,
        }
