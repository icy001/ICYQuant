"""Background scheduler — orchestrates recurring maintenance tasks.

Tasks: Checkpoint flush, Snapshot schedule, Journal cleanup, Recovery scan, State validation.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """Definition of a recurring scheduled task."""

    name: str
    interval_seconds: float
    handler: Callable
    enabled: bool = True
    last_run: Optional[float] = None


class BackgroundScheduler:
    """Runs periodic background tasks for workflow state maintenance.

    Tasks include:
      - Checkpoint flush
      - Snapshot scheduling
      - Journal cleanup
      - Recovery scanning
      - State validation
    """

    def __init__(self):
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._task_handle: Optional[asyncio.Task] = None

    # ---- Task registration --------------------------------------------------

    def register(
        self,
        name: str,
        interval_seconds: float,
        handler: Callable,
        enabled: bool = True,
    ) -> None:
        """Register a scheduled task."""
        task = ScheduledTask(
            name=name,
            interval_seconds=interval_seconds,
            handler=handler,
            enabled=enabled,
        )
        self._tasks[name] = task
        logger.info("Scheduled task registered: %s (interval=%.1fs)", name, interval_seconds)

    def unregister(self, name: str) -> None:
        """Remove a scheduled task."""
        self._tasks.pop(name, None)

    def enable(self, name: str) -> None:
        if name in self._tasks:
            self._tasks[name].enabled = True

    def disable(self, name: str) -> None:
        if name in self._tasks:
            self._tasks[name].enabled = False

    # ---- Lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        """Start the background scheduler."""
        if self._running:
            return
        self._running = True
        self._task_handle = asyncio.create_task(self._run())
        logger.info("Background scheduler started with %d tasks", len(self._tasks))

    async def stop(self) -> None:
        """Stop the background scheduler."""
        self._running = False
        if self._task_handle:
            self._task_handle.cancel()
            try:
                await self._task_handle
            except asyncio.CancelledError:
                pass
        logger.info("Background scheduler stopped")

    async def run_once(self) -> Dict[str, Any]:
        """Execute all enabled tasks once. Returns result summary."""
        results = {}
        for name, task in self._tasks.items():
            if not task.enabled:
                continue
            try:
                await task.handler()
                results[name] = "ok"
            except Exception as e:
                logger.exception("Scheduled task failed: %s", name)
                results[name] = f"error: {e}"
        return results

    # ---- Internal -----------------------------------------------------------

    async def _run(self) -> None:
        loop = asyncio.get_event_loop()
        task_timers: Dict[str, float] = {name: loop.time() for name in self._tasks}

        while self._running:
            try:
                now = loop.time()
                for name, task in self._tasks.items():
                    if not task.enabled:
                        continue
                    elapsed = now - task_timers.get(name, now)
                    if elapsed >= task.interval_seconds:
                        try:
                            await task.handler()
                            task.last_run = now
                        except Exception:
                            logger.exception("Scheduled task error: %s", name)
                        task_timers[name] = now
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Background scheduler loop error")
                await asyncio.sleep(5.0)
