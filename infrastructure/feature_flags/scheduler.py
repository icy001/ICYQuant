"""
Feature flag platform scheduler.

Provides periodic scheduling for:
    - Flag synchronization
    - Canary health checks
    - Experiment progress monitoring
    - Snapshot persistence
    - Metrics collection
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class FeatureFlagScheduler:
    """
    Periodic scheduler for feature flag platform tasks.

    Manages periodic execution of maintenance
    tasks including health checks, sync, and
    monitoring.

    Usage:
        scheduler = FeatureFlagScheduler()
        scheduler.add_task("health_check", health_check, interval=30.0)
        scheduler.add_task("sync_flags", sync_flags, interval=60.0)
        await scheduler.start()
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._task_count = 0
        self._error_count = 0
        self._scheduler_task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._running

    def add_task(
        self,
        name: str,
        coro: Callable,
        interval: float = 30.0,
        enabled: bool = True,
    ) -> None:
        """
        Add a periodic task.

        Args:
            name: Task name.
            coro: Async coroutine to execute.
            interval: Execution interval in seconds.
            enabled: Whether the task is enabled.
        """
        self._tasks[name] = {
            "coro": coro,
            "interval": interval,
            "enabled": enabled,
            "last_run": 0.0,
            "next_run": 0.0,
            "run_count": 0,
            "error_count": 0,
        }

    def remove_task(self, name: str) -> None:
        """
        Remove a task.

        Args:
            name: Task name to remove.
        """
        self._tasks.pop(name, None)

    def enable_task(self, name: str) -> None:
        """Enable a task."""
        if name in self._tasks:
            self._tasks[name]["enabled"] = True

    def disable_task(self, name: str) -> None:
        """Disable a task."""
        if name in self._tasks:
            self._tasks[name]["enabled"] = False

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._run_loop())
        logger.info(
            "Scheduler started with %d tasks",
            len(self._tasks),
        )

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        logger.info("Scheduler stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        import time

        while self._running:
            now = time.monotonic()

            for name, task in self._tasks.items():
                if not task["enabled"]:
                    continue

                if now >= task["next_run"]:
                    try:
                        result = task["coro"]()
                        if asyncio.iscoroutine(result):
                            await result
                        task["last_run"] = now
                        task["next_run"] = now + task["interval"]
                        task["run_count"] += 1
                        self._task_count += 1
                    except Exception as e:
                        task["error_count"] += 1
                        self._error_count += 1
                        logger.error(
                            "Scheduler task '%s' failed: %s", name, e,
                        )
                        # Set next run to avoid immediate retry
                        task["next_run"] = now + task["interval"]

            # Sleep briefly before next check
            await asyncio.sleep(1.0)

    def get_task_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific task."""
        if name not in self._tasks:
            return None
        task = self._tasks[name]
        return {
            "name": name,
            "enabled": task["enabled"],
            "interval": task["interval"],
            "last_run": task["last_run"],
            "next_run": task["next_run"],
            "run_count": task["run_count"],
            "error_count": task["error_count"],
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        return {
            "running": self._running,
            "total_tasks": len(self._tasks),
            "enabled_tasks": sum(
                1 for t in self._tasks.values() if t["enabled"]
            ),
            "total_runs": self._task_count,
            "total_errors": self._error_count,
            "tasks": {
                name: {
                    "enabled": t["enabled"],
                    "interval": t["interval"],
                    "run_count": t["run_count"],
                    "error_count": t["error_count"],
                }
                for name, t in self._tasks.items()
            },
        }
