"""Platform scheduler for ICYQuant service discovery.

Provides ``PlatformScheduler`` for background task scheduling
including health scans, heartbeat analysis, snapshots, recovery,
rebalancing, and metrics collection.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .runtime_context import DiscoveryContext

logger = logging.getLogger(__name__)


class ScheduledTask:
    """A scheduled background task."""

    def __init__(
        self,
        name: str,
        callback: Callable,
        interval_s: float,
        enabled: bool = True,
    ) -> None:
        self.name = name
        self.callback = callback
        self.interval_s = interval_s
        self.enabled = enabled
        self.last_run: Optional[datetime] = None
        self.run_count = 0
        self.error_count = 0
        self.last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "interval_s": self.interval_s,
            "enabled": self.enabled,
            "last_run": (
                self.last_run.isoformat()
                if self.last_run
                else None
            ),
            "run_count": self.run_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
        }


class PlatformScheduler:
    """Background task scheduler for the discovery platform.

    Manages periodic tasks like health scans, heartbeat
    analysis, snapshots, recovery, rebalancing, and metrics.
    """

    def __init__(
        self, context: Optional[DiscoveryContext] = None
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._run_count = 0

    def add_task(
        self,
        name: str,
        callback: Callable,
        interval_s: float = 30.0,
        enabled: bool = True,
    ) -> ScheduledTask:
        """Add a periodic background task.

        Args:
            name: Task name.
            callback: Task callback (sync or async).
            interval_s: Interval in seconds.
            enabled: Whether the task is initially enabled.

        Returns:
            The created ScheduledTask.
        """
        with self._lock:
            task = ScheduledTask(name, callback, interval_s, enabled)
            self._tasks[name] = task
        logger.info(
            "Scheduled task '%s' added (interval=%.1fs).",
            name,
            interval_s,
        )
        return task

    def remove_task(self, name: str) -> bool:
        with self._lock:
            if name in self._tasks:
                del self._tasks[name]
                return True
        return False

    def enable_task(self, name: str) -> bool:
        with self._lock:
            task = self._tasks.get(name)
            if task:
                task.enabled = True
                return True
        return False

    def disable_task(self, name: str) -> bool:
        with self._lock:
            task = self._tasks.get(name)
            if task:
                task.enabled = False
                return True
        return False

    async def run_task(self, name: str) -> Dict[str, Any]:
        """Manually trigger a task run.

        Args:
            name: Task name.

        Returns:
            Run result.
        """
        with self._lock:
            task = self._tasks.get(name)

        if task is None:
            return {"success": False, "error": "Task not found"}

        return await self._execute_task(task)

    async def start(self) -> None:
        """Start the scheduler."""
        with self._lock:
            if self._running:
                return
            self._running = True

        async def _loop() -> None:
            tasks = {}
            with self._lock:
                tasks = dict(self._tasks)

            next_run: Dict[str, float] = {
                name: time.monotonic()
                for name in tasks
            }

            while self._running:
                now = time.monotonic()
                for name, task in list(tasks.items()):
                    if not task.enabled:
                        continue
                    if now >= next_run.get(name, 0):
                        result = await self._execute_task(task)
                        next_run[name] = (
                            time.monotonic()
                            + task.interval_s
                        )

                await asyncio.sleep(1.0)

        self._scheduler_task = asyncio.create_task(_loop())
        logger.info("Platform scheduler started.")

    async def stop(self) -> None:
        """Stop the scheduler."""
        with self._lock:
            self._running = False
            if self._scheduler_task:
                self._scheduler_task.cancel()
                self._scheduler_task = None
        logger.info("Platform scheduler stopped.")

    async def _execute_task(
        self, task: ScheduledTask
    ) -> Dict[str, Any]:
        self._run_count += 1
        try:
            coro = task.callback()
            if asyncio.iscoroutine(coro):
                result = await coro
            else:
                result = coro
            task.run_count += 1
            task.last_run = datetime.utcnow()
            return {"success": True, "result": result}
        except Exception as exc:
            task.error_count += 1
            task.last_error = str(exc)
            logger.error(
                "Scheduled task '%s' failed: %s", task.name, exc
            )
            return {"success": False, "error": str(exc)}

    def list_tasks(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [t.to_dict() for t in self._tasks.values()]

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "task_count": len(self._tasks),
                "tasks": [
                    t.to_dict() for t in self._tasks.values()
                ],
                "total_runs": self._run_count,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"PlatformScheduler(tasks={len(self._tasks)}, "
                f"running={self._running})"
            )
