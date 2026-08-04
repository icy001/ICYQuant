"""
Configuration scheduler.

Top-level scheduler that coordinates periodic
configuration tasks:
- Scheduled reloads
- Health checks
- Integrity verification
- Metrics collection

Runs tasks at configurable intervals with
proper lifecycle management.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ScheduledTask:
    """
    A scheduled configuration task.

    Attributes:
        name: Task name.
        func: Task function.
        interval: Execution interval in seconds.
        last_run: Last execution time.
        run_count: Total executions.
        error_count: Total errors.
    """

    def __init__(
        self,
        name: str,
        func: Callable,
        interval: float,
        immediate: bool = False,
    ) -> None:
        self.name = name
        self.func = func
        self.interval = interval
        self.immediate = immediate
        self.last_run: Optional[datetime] = None
        self.run_count = 0
        self.error_count = 0
        self.last_error: Optional[str] = None
        self.last_duration: float = 0.0

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        return {
            "name": self.name,
            "interval": self.interval,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "last_duration": self.last_duration,
        }


class ConfigurationScheduler:
    """
    Configuration platform scheduler.

    Manages periodic tasks for the configuration
    platform including reloads, health checks,
    and integrity verification.

    Usage:
        scheduler = ConfigurationScheduler()
        scheduler.add_task("reload", reload_func, interval=30.0)
        scheduler.add_task("health", health_check, interval=10.0)
        scheduler.start()
        # ... later
        scheduler.stop()
    """

    def __init__(
        self,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """
        Initialize scheduler.

        Args:
            loop: Event loop for async scheduling.
        """
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._loop = loop
        self._task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()

    def add_task(
        self,
        name: str,
        func: Callable,
        interval: float,
        immediate: bool = False,
    ) -> None:
        """
        Add a scheduled task.

        Args:
            name: Task name (unique).
            func: Task function.
            interval: Execution interval in seconds.
            immediate: If True, run immediately on start.
        """
        with self._lock:
            self._tasks[name] = ScheduledTask(
                name=name,
                func=func,
                interval=interval,
                immediate=immediate,
            )

    def remove_task(
        self,
        name: str,
    ) -> bool:
        """Remove a scheduled task."""
        with self._lock:
            return self._tasks.pop(name, None) is not None

    def start(
        self,
    ) -> None:
        """Start the scheduler."""
        if self._running:
            return

        self._loop = self._loop or asyncio.get_event_loop()
        self._running = True
        self._task = self._loop.create_task(self._scheduler_loop())

    def stop(
        self,
    ) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _scheduler_loop(
        self,
    ) -> None:
        """Main scheduler loop."""
        # Run immediate tasks
        for task in list(self._tasks.values()):
            if task.immediate:
                await self._execute_task(task)

        while self._running:
            await asyncio.sleep(1.0)
            now = datetime.utcnow()

            for task in list(self._tasks.values()):
                if task.last_run is None:
                    if not task.immediate:
                        await self._execute_task(task)
                else:
                    elapsed = (now - task.last_run).total_seconds()
                    if elapsed >= task.interval:
                        await self._execute_task(task)

    async def _execute_task(
        self,
        task: ScheduledTask,
    ) -> None:
        """Execute a single scheduled task."""
        start = time.time()
        try:
            if asyncio.iscoroutinefunction(task.func):
                await task.func()
            else:
                loop = self._loop or asyncio.get_event_loop()
                await loop.run_in_executor(None, task.func)

            task.run_count += 1
            task.last_error = None
        except Exception as e:
            task.error_count += 1
            task.last_error = str(e)
        finally:
            task.last_duration = time.time() - start
            task.last_run = datetime.utcnow()

    def trigger_task(
        self,
        name: str,
    ) -> bool:
        """
        Manually trigger a task.

        Args:
            name: Task name.

        Returns:
            True if task was triggered.
        """
        if self._loop:
            task = self._tasks.get(name)
            if task:
                self._loop.create_task(self._execute_task(task))
                return True
        return False

    def get_task_status(
        self,
        name: str,
    ) -> Optional[Dict[str, Any]]:
        """Get status of a specific task."""
        task = self._tasks.get(name)
        if task:
            return task.to_dict()
        return None

    def list_tasks(
        self,
    ) -> List[Dict[str, Any]]:
        """List all scheduled tasks."""
        return [task.to_dict() for task in self._tasks.values()]

    def get_stats(
        self,
    ) -> Dict[str, Any]:
        """Get scheduler statistics."""
        return {
            "running": self._running,
            "task_count": len(self._tasks),
            "tasks": self.list_tasks(),
        }
