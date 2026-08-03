"""
Logging scheduler.

Manages periodic background tasks for the
logging platform, including metrics refresh,
health updates, and queue monitoring.

Runs as an asyncio background task with
configurable intervals.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, List, Optional

from .metrics import LoggingMetrics


class LoggingScheduler:
    """
    Background logging scheduler.

    Runs periodic tasks:
    - Metrics refresh (update queue/buffer sizes)
    - Health check update
    - Queue monitoring

    Usage:
        scheduler = LoggingScheduler(
            metrics=metrics,
            pipeline=pipeline,
            interval=5.0,
        )
        await scheduler.start()
        # ... runs in background ...
        await scheduler.stop()
    """

    def __init__(
        self,
        metrics: Optional[LoggingMetrics] = None,
        pipeline: Any = None,
        interval: float = 5.0,
        tasks: Optional[List[Callable]] = None,
    ) -> None:
        """
        Initialize scheduler.

        Args:
            metrics: LoggingMetrics to update.
            pipeline: LoggingPipeline for queue stats.
            interval: Tick interval in seconds.
            tasks: Additional periodic tasks.
        """

        self._metrics = metrics
        self._pipeline = pipeline
        self._interval = interval
        self._tasks: List[Callable] = tasks or []
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._tick_count: int = 0

    @property
    def is_running(
        self,
    ) -> bool:
        """Check if scheduler is running."""
        return self._running

    @property
    def tick_count(
        self,
    ) -> int:
        """Get total tick count."""
        return self._tick_count

    def add_task(
        self,
        task: Callable,
    ) -> None:
        """
        Add a periodic task.

        Args:
            task: Callable to execute each tick.
        """

        self._tasks.append(task)

    async def start(
        self,
    ) -> None:
        """Start the scheduler."""

        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(
            self._run_loop()
        )

    async def stop(
        self,
    ) -> None:
        """Stop the scheduler."""

        self._running = False

        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_loop(
        self,
    ) -> None:
        """Background scheduler loop."""

        while self._running:
            try:
                await self._tick()
                self._tick_count += 1
            except asyncio.CancelledError:
                break
            except Exception:
                pass

            await asyncio.sleep(self._interval)

    async def _tick(
        self,
    ) -> None:
        """Execute one scheduler tick."""

        # Update metrics from pipeline
        if self._metrics is not None and self._pipeline is not None:
            self._metrics.update_queue_size(
                self._pipeline.queue.size()
            )
            self._metrics.update_buffer_size(
                self._pipeline.buffer.size
            )

        # Run custom tasks
        for task in self._tasks:
            try:
                result = task()
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

    def get_status(
        self,
    ) -> dict:
        """Get scheduler status."""

        return {
            "running": self._running,
            "interval": self._interval,
            "tick_count": self._tick_count,
            "tasks": len(self._tasks),
        }
