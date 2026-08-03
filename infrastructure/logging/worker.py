"""
Background logging worker.

Runs a background asyncio task that
continuously collects batches from the
queue and dispatches them to handlers
via the dispatcher.

The worker provides graceful start/stop
lifecycle management and error recovery.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from .batch import BatchCollector
from .dispatcher import LogDispatcher


class LoggingWorker:
    """
    Background log processing worker.

    Runs in a background asyncio task,
    continuously:
    1. Collecting a batch from the queue
    2. Dispatching the batch to all handlers

    The worker recovers from errors
    automatically, ensuring the logging
    pipeline stays operational.

    Usage:
        worker = LoggingWorker(
            collector=collector,
            dispatcher=dispatcher,
        )
        await worker.start()
        # ... runs in background ...
        await worker.stop()
    """

    def __init__(
        self,
        collector: BatchCollector,
        dispatcher: LogDispatcher,
        name: str = "log-worker",
    ) -> None:
        """
        Initialize worker.

        Args:
            collector: BatchCollector for collecting from queue.
            dispatcher: LogDispatcher for dispatching to handlers.
            name: Worker name.
        """

        self._collector = collector
        self._dispatcher = dispatcher
        self._name = name
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._cycle_count: int = 0
        self._error_count: int = 0

    @property
    def is_running(
        self,
    ) -> bool:
        """Check if worker is running."""
        return self._running

    @property
    def cycle_count(
        self,
    ) -> int:
        """Get total cycle count."""
        return self._cycle_count

    @property
    def error_count(
        self,
    ) -> int:
        """Get total error count."""
        return self._error_count

    async def start(
        self,
    ) -> None:
        """
        Start the worker.

        Launches the background processing
        loop as an asyncio task.
        """

        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(
            self._run_loop()
        )

    async def stop(
        self,
    ) -> None:
        """
        Stop the worker.

        Signals the background loop to stop
        and waits for completion.
        """

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
        """Background processing loop."""

        while self._running:
            try:
                batch = await self._collector.collect()
                if batch:
                    await self._dispatcher.dispatch(batch)
                    self._cycle_count += 1
            except asyncio.CancelledError:
                break
            except Exception:
                self._error_count += 1
                await asyncio.sleep(0.1)

    async def process_once(
        self,
    ) -> None:
        """
        Process a single batch.

        Useful for testing or manual triggers.
        """

        try:
            batch = await self._collector.collect()
            if batch:
                await self._dispatcher.dispatch(batch)
                self._cycle_count += 1
        except Exception:
            self._error_count += 1

    def get_stats(
        self,
    ) -> dict:
        """
        Get worker statistics.

        Returns:
            Statistics dictionary.
        """

        return {
            "name": self._name,
            "running": self._running,
            "cycle_count": self._cycle_count,
            "error_count": self._error_count,
            "collector": self._collector.get_stats(),
            "dispatcher": self._dispatcher.get_stats(),
        }
