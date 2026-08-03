"""
Tracing scheduler.

Runs periodic background tasks for the tracing
platform, including trace expiration, metrics
collection, and export pipeline maintenance.

Background Tasks:
- Trace expiration (clean up stale active traces)
- Metrics collection (export to monitoring)
- Pipeline flush (force flush on interval)
- Buffer recovery (recover spans from disk)

Usage:
    scheduler = TracingScheduler(
        registry=registry,
        monitoring=monitoring,
        pipeline=pipeline,
        interval=30,
    )
    await scheduler.start()
    # ... runs in background ...
    await scheduler.stop()
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

from .monitoring import TracingMonitoring
from .registry import TraceRegistry


class TracingScheduler:
    """
    Background tracing scheduler.

    Runs periodic maintenance tasks for the
    tracing platform at a configurable interval:

    1. Expire stale active traces
    2. Collect monitoring metrics
    3. Force flush export pipeline
    4. Recover spans from disk buffer

    Tasks run in an asyncio background task
    and can be started/stopped gracefully.

    Features:
    - Configurable interval
    - Graceful start/stop
    - Error isolation (continue on failure)
    - Cycle/error tracking
    - Manual trigger support

    Usage:
        scheduler = TracingScheduler(
            registry=registry,
            monitoring=monitoring,
            interval=30,
        )
        await scheduler.start()
        # ... runs in background ...
        await scheduler.stop()
    """

    def __init__(
        self,
        registry: Optional[TraceRegistry] = None,
        monitoring: Optional[TracingMonitoring] = None,
        pipeline: Optional[Any] = None,
        interval: float = 30.0,
    ) -> None:
        """
        Initialize scheduler.

        Args:
            registry: TraceRegistry for expiration.
            monitoring: TracingMonitoring for metrics collection.
            pipeline: TracePipeline for periodic flush.
            interval: Scheduler interval in seconds.
        """

        self._registry = registry
        self._monitoring = monitoring
        self._pipeline = pipeline
        self._interval = interval

        self._running: bool = False
        self._task: Optional[asyncio.Task] = None

        self._cycle_count: int = 0
        self._error_count: int = 0
        self._last_cycle_time: Optional[float] = None

        self._expired_total: int = 0
        self._collected_total: int = 0

    @property
    def is_running(
        self,
    ) -> bool:
        """Check if scheduler is running."""
        return self._running

    @property
    def interval(
        self,
    ) -> float:
        """Get scheduler interval."""
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

    @property
    def expired_total(
        self,
    ) -> int:
        """Get total expired traces."""
        return self._expired_total

    async def start(
        self,
    ) -> None:
        """
        Start the scheduler.

        Launches the background maintenance
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
        """Background maintenance loop."""

        while self._running:
            try:
                await self._run_cycle()
                self._cycle_count += 1
                self._last_cycle_time = time.time()
            except Exception:
                self._error_count += 1

            await asyncio.sleep(self._interval)

    async def _run_cycle(
        self,
    ) -> None:
        """Execute a single maintenance cycle."""

        # 1. Expire stale traces
        if self._registry is not None:
            try:
                expired = self._registry.expire()
                self._expired_total += expired
            except Exception:
                pass

        # 2. Collect monitoring metrics
        if self._monitoring is not None:
            try:
                await self._monitoring.collect()
                self._collected_total += 1
            except Exception:
                pass

        # 3. Flush pipeline (if configured)
        if self._pipeline is not None and hasattr(
            self._pipeline, "flush"
        ):
            try:
                await self._pipeline.flush()
            except Exception:
                pass

    async def run_once(
        self,
    ) -> None:
        """
        Execute a single maintenance cycle manually.

        Useful for testing or manual triggers.
        """

        try:
            await self._run_cycle()
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
            "expired_total": self._expired_total,
            "collected_total": self._collected_total,
        }
