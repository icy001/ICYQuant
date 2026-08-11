"""
Streaming Runtime — worker pool and execution environment for the
real-time streaming platform.

Commit 16 Part 1.4
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StreamingRuntimeStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class StreamingRuntimeConfig:
    """Configuration for the streaming runtime worker pool."""
    max_workers: int = 8
    max_queue_size: int = 100000
    worker_timeout_ms: int = 30000
    pause_on_backpressure: bool = True
    metrics_enabled: bool = True


@dataclass
class WorkerStats:
    """Statistics for a single worker."""
    worker_id: int
    processed: int = 0
    errors: int = 0
    avg_latency_ms: float = 0.0
    busy: bool = False
    last_event_at: float = 0.0


class StreamingRuntime:
    """
    Worker pool and execution environment for the streaming platform.

    Manages concurrent event processing with configurable worker count,
    queue size limits, and backpressure-aware scheduling.

    Usage::

        runtime = StreamingRuntime(StreamingRuntimeConfig(max_workers=4))
        await runtime.start()
        await runtime.submit(handler, event)
        stats = await runtime.stats()
        await runtime.stop()
    """

    def __init__(self, config: Optional[StreamingRuntimeConfig] = None) -> None:
        self.config = config or StreamingRuntimeConfig()
        self._status = StreamingRuntimeStatus.IDLE
        self._queue: asyncio.Queue[tuple[Any, Any]] = asyncio.Queue(
            maxsize=self.config.max_queue_size,
        )
        self._workers: list[asyncio.Task[None]] = []
        self._worker_stats: dict[int, WorkerStats] = {}
        self._lock = asyncio.Lock()
        self._paused = asyncio.Event()
        self._paused.set()

    async def start(self) -> None:
        """Start the runtime worker pool."""
        self._status = StreamingRuntimeStatus.RUNNING
        self._paused.set()

        for i in range(self.config.max_workers):
            stats = WorkerStats(worker_id=i)
            self._worker_stats[i] = stats
            task = asyncio.create_task(self._worker_loop(i, stats))
            self._workers.append(task)

        logger.info("StreamingRuntime started with %d workers.", self.config.max_workers)

    async def stop(self) -> None:
        """Gracefully stop the runtime."""
        self._status = StreamingRuntimeStatus.STOPPING
        logger.info("Stopping StreamingRuntime...")

        # Drain remaining items
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break

        # Cancel workers
        for task in self._workers:
            task.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)

        self._workers.clear()
        self._status = StreamingRuntimeStatus.STOPPED
        logger.info("StreamingRuntime stopped.")

    async def submit(self, handler: Any, event: Any) -> None:
        """Submit an event for processing by the worker pool."""
        if self._status != StreamingRuntimeStatus.RUNNING:
            raise RuntimeError("Runtime is not running")

        await self._paused.wait()

        try:
            self._queue.put_nowait((handler, event))
        except asyncio.QueueFull:
            if self.config.pause_on_backpressure:
                self._paused.clear()
                logger.warning("Queue full (%d), pausing submissions.", self.config.max_queue_size)
            await self._queue.put((handler, event))

    async def submit_batch(self, items: list[tuple[Any, Any]]) -> None:
        """Submit a batch of (handler, event) tuples."""
        for handler, event in items:
            await self.submit(handler, event)

    async def pause(self) -> None:
        """Pause all worker processing."""
        self._paused.clear()
        self._status = StreamingRuntimeStatus.PAUSED
        logger.info("StreamingRuntime paused.")

    async def resume(self) -> None:
        """Resume worker processing."""
        self._paused.set()
        self._status = StreamingRuntimeStatus.RUNNING
        logger.info("StreamingRuntime resumed.")

    async def _worker_loop(self, worker_id: int, stats: WorkerStats) -> None:
        """Main worker loop."""
        logger.debug("Worker %d started.", worker_id)
        try:
            while self._status in (
                StreamingRuntimeStatus.RUNNING,
                StreamingRuntimeStatus.PAUSED,
            ):
                try:
                    handler, event = await asyncio.wait_for(
                        self._queue.get(), timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    continue

                stats.busy = True
                stats.last_event_at = time.monotonic()
                start = time.monotonic()

                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                    stats.processed += 1
                except Exception:
                    stats.errors += 1
                    logger.exception("Worker %d error processing event.", worker_id)
                finally:
                    elapsed = (time.monotonic() - start) * 1000
                    # Exponential moving average latency
                    stats.avg_latency_ms = (
                        0.9 * stats.avg_latency_ms + 0.1 * elapsed
                    )
                    stats.busy = False
                    self._queue.task_done()

        except asyncio.CancelledError:
            pass
        logger.debug("Worker %d stopped. processed=%d errors=%d", worker_id, stats.processed, stats.errors)

    async def stats(self) -> dict[str, Any]:
        """Get runtime statistics."""
        return {
            "status": self._status.value,
            "workers": self.config.max_workers,
            "queue_size": self._queue.qsize(),
            "max_queue_size": self.config.max_queue_size,
            "paused": not self._paused.is_set(),
            "workers_detail": [
                {
                    "id": s.worker_id,
                    "processed": s.processed,
                    "errors": s.errors,
                    "avg_latency_ms": round(s.avg_latency_ms, 2),
                    "busy": s.busy,
                }
                for s in self._worker_stats.values()
            ],
            "total_processed": sum(s.processed for s in self._worker_stats.values()),
            "total_errors": sum(s.errors for s in self._worker_stats.values()),
        }

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def is_paused(self) -> bool:
        return not self._paused.is_set()
