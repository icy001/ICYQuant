"""
Log batch collector.

Collects log records from the queue
into batches for efficient processing,
reducing per-record overhead for
high-volume log streams.

Batches are collected until either:
- Maximum batch size is reached, OR
- Collection timeout expires
"""

from __future__ import annotations

import asyncio
from typing import List

from .models import LogEntry
from .queue import LogQueue


class BatchCollector:
    """
    Log batch collector.

    Collects log records from the queue
    into batches, balancing latency and
    throughput:

    - Larger batches = higher throughput, higher latency
    - Smaller batches = lower latency, lower throughput
    - Timeout ensures minimum flush frequency

    Usage:
        collector = BatchCollector(
            queue=queue,
            batch_size=100,
            timeout=1.0,
        )
        batch = await collector.collect()
    """

    def __init__(
        self,
        queue: LogQueue,
        batch_size: int = 100,
        timeout: float = 1.0,
    ) -> None:
        """
        Initialize batch collector.

        Args:
            queue: LogQueue to collect from.
            batch_size: Maximum records per batch.
            timeout: Maximum wait time in seconds.
        """

        self._queue = queue
        self._batch_size = batch_size
        self._timeout = timeout
        self._total_batches: int = 0
        self._total_records: int = 0

    @property
    def batch_size(
        self,
    ) -> int:
        """Get max batch size."""
        return self._batch_size

    @property
    def timeout(
        self,
    ) -> float:
        """Get timeout."""
        return self._timeout

    @property
    def total_batches(
        self,
    ) -> int:
        """Get total batches collected."""
        return self._total_batches

    @property
    def total_records(
        self,
    ) -> int:
        """Get total records collected."""
        return self._total_records

    async def collect(
        self,
    ) -> List[LogEntry]:
        """
        Collect a batch of log records.

        Waits for the first record, then
        collects additional records up to
        batch_size or until timeout.

        Returns:
            List of LogEntry records.
        """

        batch: List[LogEntry] = []

        # Wait for first record (blocking)
        first = await self._queue.get()
        batch.append(first)

        # Collect remaining with timeout
        while len(batch) < self._batch_size:
            try:
                record = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=self._timeout,
                )
                batch.append(record)
            except asyncio.TimeoutError:
                break
            except Exception:
                break

        self._total_batches += 1
        self._total_records += len(batch)

        return batch

    def get_stats(
        self,
    ) -> dict:
        """
        Get collector statistics.

        Returns:
            Statistics dictionary.
        """

        avg_batch = (
            self._total_records / self._total_batches
            if self._total_batches > 0
            else 0
        )
        return {
            "batch_size": self._batch_size,
            "timeout": self._timeout,
            "total_batches": self._total_batches,
            "total_records": self._total_records,
            "avg_batch_size": round(avg_batch, 2),
        }
