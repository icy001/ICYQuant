"""Security scheduler for ICYQuant Service Mesh.

Provides ``SecurityScheduler`` for background tasks including
certificate rotation, policy sync, CRL refresh, key rotation,
and metrics flush.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SecurityScheduledTask:
    """A scheduled security background task."""

    def __init__(
        self,
        name: str,
        fn: Callable,
        interval_s: float = 300.0,
        enabled: bool = True,
    ) -> None:
        self.name = name
        self.fn = fn
        self.interval_s = interval_s
        self.enabled = enabled
        self.last_run: Optional[float] = None
        self.run_count = 0
        self.error_count = 0
        self.last_error = ""


class SecurityScheduler:
    """Schedules security background tasks."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tasks: Dict[str, SecurityScheduledTask] = {}
        self._running = False
        self._task_handles: Dict[str, asyncio.Task] = {}

    def register_task(
        self,
        name: str,
        fn: Callable,
        interval_s: float = 300.0,
        enabled: bool = True,
    ) -> None:
        with self._lock:
            self._tasks[name] = SecurityScheduledTask(
                name, fn, interval_s, enabled
            )

    def unregister_task(self, name: str) -> bool:
        with self._lock:
            if name in self._tasks:
                del self._tasks[name]
                return True
            return False

    def enable_task(self, name: str) -> bool:
        with self._lock:
            if name in self._tasks:
                self._tasks[name].enabled = True
                return True
            return False

    def disable_task(self, name: str) -> bool:
        with self._lock:
            if name in self._tasks:
                self._tasks[name].enabled = False
                return True
            return False

    async def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            loop = asyncio.get_event_loop()
            for name, task in self._tasks.items():
                if task.enabled:
                    handle = loop.create_task(self._run_task(task))
                    self._task_handles[name] = handle

    async def stop(self) -> None:
        with self._lock:
            self._running = False
            for handle in self._task_handles.values():
                handle.cancel()
            self._task_handles.clear()

    async def _run_task(self, task: SecurityScheduledTask) -> None:
        while self._running and task.enabled:
            try:
                if task.last_run is None:
                    task.last_run = 0.0
                elapsed = time.monotonic() - task.last_run
                if elapsed >= task.interval_s:
                    result = task.fn()
                    if asyncio.iscoroutine(result):
                        await result
                    task.last_run = time.monotonic()
                    task.run_count += 1
            except Exception as exc:
                task.error_count += 1
                task.last_error = str(exc)
                logger.warning("Security task '%s' failed: %s", task.name, exc)
            await asyncio.sleep(min(1.0, task.interval_s / 2))

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def get_task_status(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            task = self._tasks.get(name)
            if not task:
                return None
            return {
                "name": task.name,
                "enabled": task.enabled,
                "interval_s": task.interval_s,
                "last_run": task.last_run,
                "run_count": task.run_count,
                "error_count": task.error_count,
                "last_error": task.last_error,
            }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "task_count": len(self._tasks),
                "tasks": [self.get_task_status(name) for name in self._tasks],
            }
