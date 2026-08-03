"""
Monitoring scheduler.

Runs periodic background collection cycles
at a configurable interval, providing
start/stop lifecycle management for the
monitoring service.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

from .service import MonitoringService


class MonitoringScheduler:
    """
    Background monitoring scheduler.

    Runs the monitoring collect cycle
    at a fixed interval in an asyncio
    background task.

    Usage:
        scheduler = MonitoringScheduler(
            service=service,
            interval=15,
        )
        await scheduler.start()
        # ... runs in background ...
        await scheduler.stop()
    """

    def __init__(
        self,
        service: MonitoringService,
        interval: int = 15,
    ) -> None:
        """
        Initialize scheduler.

        Args:
            service: MonitoringService instance.
            interval: Collection interval in seconds.
        """

        self._service = service
        self._interval = interval
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._cycle_count: int = 0
        self._last_cycle_time: Optional[float] = None
        self._error_count: int = 0

    @property
    def is_running(
        self,
    ) -> bool:
        """Check if scheduler is running."""
        return self._running

    @property
    def interval(
        self,
    ) -> int:
        """Get collection interval."""
        return self._interval

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
        Start the scheduler.

        Launches the background collection
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
        Stop the scheduler.

        Signals the background loop to stop
        and waits for it to complete.
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
        """Background collection loop."""

        while self._running:
            try:
                await self._service.collect()
                self._cycle_count += 1
                self._last_cycle_time = time.time()
            except Exception:
                self._error_count += 1

            await asyncio.sleep(self._interval)

    async def run_once(
        self,
    ) -> None:
        """
        Execute a single collection cycle.

        Useful for testing or manual triggers.
        """

        try:
            await self._service.collect()
            self._cycle_count += 1
            self._last_cycle_time = time.time()
        except Exception:
            self._error_count += 1

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get scheduler status.

        Returns:
            Status dictionary.
        """

        return {
            "running": self._running,
            "interval": self._interval,
            "cycle_count": self._cycle_count,
            "error_count": self._error_count,
            "last_cycle_time": self._last_cycle_time,
        }
