from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class PluginScheduler:
    """Background task scheduler for periodic plugin framework tasks.

    Manages a set of named tasks that execute at configurable intervals
    via ``asyncio.create_task``.  Supports graceful shutdown and
    on-demand execution.

    Default tasks:

    - ``repository_sync`` every 60 s
    - ``plugin_update_check`` every 300 s
    - ``health_check`` every 30 s
    - ``snapshot_cleanup`` every 3600 s
    - ``metrics_collection`` every 10 s
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._stats: Dict[str, int] = {
            "scheduled": 0,
            "completed": 0,
            "failed": 0,
            "overdue": 0,
        }

    async def start(self) -> None:
        """Start the scheduler and all registered tasks."""
        if self._running:
            logger.debug("Scheduler is already running.")
            return

        self._shutdown_event.clear()
        self._running = True
        self._stats["scheduled"] = 0

        for name, task_info in list(self._tasks.items()):
            self._schedule_task(name, task_info)

        logger.info(
            "Scheduler started with %d task(s).", len(self._tasks)
        )

    async def stop(self) -> None:
        """Stop the scheduler and cancel all running tasks."""
        if not self._running:
            return

        logger.info("Stopping scheduler...")
        self._shutdown_event.set()
        self._running = False

        for name, task_info in list(self._tasks.items()):
            task = task_info.get("_asyncio_task")
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            task_info["_asyncio_task"] = None

        logger.info("Scheduler stopped.")

    def is_running(self) -> bool:
        """Check whether the scheduler is active.

        Returns:
            ``True`` if the scheduler is running.
        """
        return self._running

    def add_task(
        self, name: str, fn: Callable, interval: float
    ) -> None:
        """Register a periodic task.

        Args:
            name: Unique task identifier.
            fn: The coroutine or function to invoke.
            interval: Interval in seconds between executions.
        """
        if name in self._tasks:
            logger.warning(
                "Task '%s' already exists; replacing.", name
            )
        self._tasks[name] = {
            "fn": fn,
            "interval": interval,
            "_asyncio_task": None,
        }
        self._stats["scheduled"] += 1

        if self._running:
            self._schedule_task(name, self._tasks[name])

        logger.debug(
            "Added task '%s' (interval=%.1fs).", name, interval
        )

    def remove_task(self, name: str) -> None:
        """Remove a registered task and cancel its running instance.

        Args:
            name: The task identifier to remove.
        """
        task_info = self._tasks.pop(name, None)
        if task_info is None:
            logger.warning("Task '%s' not found for removal.", name)
            return

        task = task_info.get("_asyncio_task")
        if task is not None and not task.done():
            task.cancel()

        logger.info("Removed task '%s'.", name)

    def get_tasks(self) -> List[Dict[str, Any]]:
        """Return the list of registered tasks and their metadata.

        Returns:
            Sorted list of task info dictionaries.
        """
        result: List[Dict[str, Any]] = []
        for name in sorted(self._tasks.keys()):
            info = self._tasks[name]
            result.append({
                "name": name,
                "interval": info["interval"],
                "running": (
                    info["_asyncio_task"] is not None
                    and not info["_asyncio_task"].done()
                ),
            })
        return result

    async def run_task(self, name: str) -> Any:
        """Execute a registered task immediately.

        Args:
            name: The task identifier.

        Returns:
            The return value of the task function.

        Raises:
            KeyError: If the task is not found.
        """
        task_info = self._tasks.get(name)
        if task_info is None:
            raise KeyError(f"Task '{name}' not found.")

        fn = task_info["fn"]
        try:
            result = fn()
            if asyncio.iscoroutine(result):
                result = await result
            self._stats["completed"] += 1
            logger.debug("Task '%s' completed.", name)
            return result
        except Exception as e:
            self._stats["failed"] += 1
            logger.error("Task '%s' failed: %s", name, e)
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics.

        Returns:
            A dictionary with run state and counters.
        """
        return {
            "running": self._running,
            "task_count": len(self._tasks),
            "tasks": self.get_tasks(),
            "stats": dict(self._stats),
        }

    def _schedule_task(
        self, name: str, task_info: Dict[str, Any]
    ) -> None:
        """Schedule the asyncio task loop for a registered task.

        Args:
            name: Task identifier.
            task_info: Task metadata dict.
        """
        interval = task_info["interval"]
        fn = task_info["fn"]

        async def _run_loop() -> None:
            while not self._shutdown_event.is_set():
                try:
                    result = fn()
                    if asyncio.iscoroutine(result):
                        result = await result
                    self._stats["completed"] += 1
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self._stats["failed"] += 1
                    logger.error(
                        "Task '%s' failed: %s", name, e
                    )
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=interval,
                    )
                except asyncio.TimeoutError:
                    pass

        asyncio_task = asyncio.create_task(_run_loop())
        task_info["_asyncio_task"] = asyncio_task