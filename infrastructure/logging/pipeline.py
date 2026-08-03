"""
Async logging pipeline.

Orchestrates the complete async logging
pipeline, wiring together the queue,
batch collector, dispatcher, worker,
and buffer into a unified component.

Pipeline flow:
    Logger → Queue → BatchCollector → Dispatcher → Handlers

The pipeline provides a single start/stop
lifecycle and exposes metrics for
monitoring integration.

Usage:
    pipeline = LoggingPipeline(
        handlers=[ConsoleHandler(), FileHandler(...)],
        queue_size=10000,
        batch_size=100,
        flush_interval=1.0,
    )
    await pipeline.start()

    # Log records via the pipeline's logger
    await pipeline.log(entry)

    await pipeline.stop()
"""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional

from .batch import BatchCollector
from .buffer import MemoryBuffer
from .dispatcher import LogDispatcher
from .handlers import LogHandler
from .metrics import LoggingMetrics
from .models import LogEntry
from .policy import BackpressurePolicy
from .queue import LogQueue
from .worker import LoggingWorker


class LoggingPipeline:
    """
    Async logging pipeline.

    Combines queue, batch collector,
    dispatcher, worker, and buffer into
    a single managed component.

    Features:
    - Non-blocking log submission
    - Batch processing for throughput
    - Backpressure with configurable policy
    - Memory buffer for overflow
    - Metrics tracking
    - Graceful start/stop lifecycle

    Usage:
        pipeline = LoggingPipeline(
            handlers=[ConsoleHandler()],
        )
        await pipeline.start()

        entry = build_record("INFO", "app", "Hello")
        await pipeline.log(entry)

        await pipeline.stop()
    """

    def __init__(
        self,
        handlers: Optional[List[LogHandler]] = None,
        queue_size: int = 10000,
        batch_size: int = 100,
        flush_interval: float = 1.0,
        backpressure: BackpressurePolicy = BackpressurePolicy.BLOCK,
        buffer_capacity: int = 50000,
        buffer_strategy: str = "ring",
    ) -> None:
        """
        Initialize pipeline.

        Args:
            handlers: List of log handlers.
            queue_size: Maximum queue size.
            batch_size: Maximum batch size.
            flush_interval: Batch collection timeout in seconds.
            backpressure: Backpressure policy.
            buffer_capacity: Memory buffer capacity.
            buffer_strategy: Buffer eviction strategy.
        """

        self._handlers = handlers or []
        self._metrics = LoggingMetrics()

        # Create components
        self._queue = LogQueue(
            max_size=queue_size,
            policy=backpressure,
        )
        self._collector = BatchCollector(
            queue=self._queue,
            batch_size=batch_size,
            timeout=flush_interval,
        )
        self._dispatcher = LogDispatcher(
            handlers=self._handlers,
            metrics=self._metrics,
        )
        self._worker = LoggingWorker(
            collector=self._collector,
            dispatcher=self._dispatcher,
        )
        self._buffer = MemoryBuffer(
            capacity=buffer_capacity,
            strategy=buffer_strategy,
        )

        self._started: bool = False

    @property
    def queue(
        self,
    ) -> LogQueue:
        """Get the log queue."""
        return self._queue

    @property
    def collector(
        self,
    ) -> BatchCollector:
        """Get the batch collector."""
        return self._collector

    @property
    def dispatcher(
        self,
    ) -> LogDispatcher:
        """Get the dispatcher."""
        return self._dispatcher

    @property
    def worker(
        self,
    ) -> LoggingWorker:
        """Get the worker."""
        return self._worker

    @property
    def buffer(
        self,
    ) -> MemoryBuffer:
        """Get the memory buffer."""
        return self._buffer

    @property
    def metrics(
        self,
    ) -> LoggingMetrics:
        """Get pipeline metrics."""
        return self._metrics

    @property
    def is_started(
        self,
    ) -> bool:
        """Check if pipeline is started."""
        return self._started

    def add_handler(
        self,
        handler: LogHandler,
    ) -> None:
        """
        Add a handler.

        Args:
            handler: Handler to add.
        """

        self._handlers.append(handler)
        self._dispatcher.add_handler(handler)

    async def log(
        self,
        record: LogEntry,
    ) -> bool:
        """
        Submit a log record to the pipeline.

        Non-blocking (unless BLOCK policy and queue is full).
        Updates metrics automatically.

        Args:
            record: LogEntry to log.

        Returns:
            True if accepted, False if dropped.
        """

        accepted = await self._queue.put(record)

        if accepted:
            self._metrics.record_queued()
        else:
            # Spill to buffer if dropped
            self._buffer.add(record)
            self._metrics.record_dropped()

        self._metrics.update_queue_size(self._queue.size())
        self._metrics.update_buffer_size(self._buffer.size)

        return accepted

    def log_nowait(
        self,
        record: LogEntry,
    ) -> bool:
        """
        Non-async log submission.

        Args:
            record: LogEntry to log.

        Returns:
            True if accepted, False if dropped.
        """

        accepted = self._queue.put_nowait(record)

        if accepted:
            self._metrics.record_queued()
        else:
            self._buffer.add(record)
            self._metrics.record_dropped()

        return accepted

    async def start(
        self,
    ) -> None:
        """
        Start the pipeline.

        Starts the background worker and all handlers.
        """

        if self._started:
            return

        # Start handlers
        for handler in self._handlers:
            await handler.startup()

        # Start worker
        await self._worker.start()

        self._started = True

    async def stop(
        self,
    ) -> None:
        """
        Stop the pipeline.

        Stops the worker and flushes remaining records.
        """

        if not self._started:
            return

        # Stop worker
        await self._worker.stop()

        # Flush remaining queue
        await self._flush_remaining()

        # Shutdown handlers
        for handler in self._handlers:
            await handler.shutdown()

        self._started = False

    async def _flush_remaining(
        self,
    ) -> None:
        """Flush remaining records in the queue."""

        while not self._queue.is_empty():
            batch = self._collector.collect()
            if asyncio.iscoroutine(batch):
                batch = await batch
            if batch:
                await self._dispatcher.dispatch(batch)

        # Drain buffer
        buffered = self._buffer.drain()
        if buffered:
            await self._dispatcher.dispatch(buffered)

    def get_status(
        self,
    ) -> dict:
        """
        Get pipeline status.

        Returns:
            Status dictionary.
        """

        return {
            "started": self._started,
            "queue": self._queue.get_stats(),
            "collector": self._collector.get_stats(),
            "dispatcher": self._dispatcher.get_stats(),
            "worker": self._worker.get_stats(),
            "buffer": self._buffer.get_stats(),
            "metrics": self._metrics.to_dict(),
            "handlers": len(self._handlers),
        }
