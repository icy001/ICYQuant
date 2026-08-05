"""Health scheduler for ICYQuant service discovery.

Provides ``HealthScheduler`` for running periodic background tasks
such as heartbeat checks, health checks, lease cleanup, recovery
checks, and metrics collection. Tasks are scheduled as asyncio
coroutines.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from .exceptions import ServiceDiscoveryError

logger = logging.getLogger(__name__)


class HealthScheduler:
    """Scheduler for periodic service discovery health tasks.

    Tasks are registered with a name, a callable (sync or async),
    and an interval. The scheduler runs each task in its own asyncio
    task loop with the configured interval.

    Default tasks (registered via :meth:`_register_defaults` when
    ``register_defaults=True``):
        - heartbeat_check (5s)
        - health_check (10s)
        - lease_cleanup (15s)
        - recovery_check (30s)
        - metrics_collection (10s)
    """

    DEFAULT_TASKS = (
        ("heartbeat_check", 5.0),
        ("health_check", 10.0),
        ("lease_cleanup", 15.0),
        ("recovery_check", 30.0),
        ("metrics_collection", 10.0),
    )

    def __init__(self, register_defaults: bool = False) -> None:
        self._lock = threading.RLock()
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._async_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._exec_count: Dict[str, int] = {}
        self._failure_count: Dict[str, int] = {}
        self._last_run: Dict[str, float] = {}
        if register_defaults:
            self._register_defaults()

    # ── Public API ──

    async def start(self) -> None:
        """Start all registered tasks.

        Raises:
            ServiceDiscoveryError: If already running.
        """
        with self._lock:
            if self._running:
                raise ServiceDiscoveryError(
                    "HealthScheduler is already running."
                )
            self._running = True
            tasks = list(self._tasks.items())
        for name, spec in tasks:
            self._async_tasks[name] = asyncio.create_task(
                self._run_loop(name, spec)
            )
        logger.info(
            "HealthScheduler started with %d task(s).", len(self._async_tasks)
        )

    async def stop(self) -> None:
        """Stop all running tasks gracefully."""
        with self._lock:
            self._running = False
            tasks = list(self._async_tasks.values())
            self._async_tasks.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("HealthScheduler stopped.")

    def is_running(self) -> bool:
        """Return whether the scheduler is currently running."""
        with self._lock:
            return self._running

    def add_task(
        self, name: str, fn: Callable, interval: float
    ) -> None:
        """Register a periodic task.

        Args:
            name: Unique task name.
            fn: Callable (sync or async) to execute.
            interval: Execution interval in seconds.
        """
        if not name:
            raise ServiceDiscoveryError("Task name must be non-empty.")
        if not callable(fn):
            raise ServiceDiscoveryError("Task must be callable.")
        effective_interval = float(interval) if interval > 0 else 5.0
        with self._lock:
            self._tasks[name] = {
                "fn": fn,
                "interval": effective_interval,
                "added_at": time.time(),
            }
            self._exec_count.setdefault(name, 0)
            self._failure_count.setdefault(name, 0)
        if self._running:
            self._async_tasks[name] = asyncio.create_task(
                self._run_loop(name, self._tasks[name])
            )
        logger.info(
            "Added task '%s' (interval=%.2fs).", name, effective_interval
        )

    def remove_task(self, name: str) -> None:
        """Remove a registered task."""
        with self._lock:
            self._tasks.pop(name, None)
            self._exec_count.pop(name, None)
            self._failure_count.pop(name, None)
            self._last_run.pop(name, None)
            task = self._async_tasks.pop(name, None)
        if task is not None and not task.done():
            task.cancel()
        logger.info("Removed task '%s'.", name)

    def get_tasks(self) -> List[Dict[str, Any]]:
        """Return a list of registered task descriptors."""
        with self._lock:
            return [
                {
                    "name": name,
                    "interval": spec["interval"],
                    "added_at": spec["added_at"],
                    "exec_count": self._exec_count.get(name, 0),
                    "failure_count": self._failure_count.get(name, 0),
                    "last_run": self._last_run.get(name, 0.0),
                }
                for name, spec in self._tasks.items()
            ]

    async def run_task(self, name: str) -> Any:
        """Run a registered task immediately once.

        Args:
            name: The task name.

        Returns:
            The task's return value.

        Raises:
            ServiceDiscoveryError: If the task is not registered.
        """
        with self._lock:
            spec = self._tasks.get(name)
        if spec is None:
            raise ServiceDiscoveryError(f"Task '{name}' is not registered.")
        return await self._invoke(name, spec["fn"])

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the scheduler."""
        with self._lock:
            return {
                "running": self._running,
                "task_count": len(self._tasks),
                "exec_count": dict(self._exec_count),
                "failure_count": dict(self._failure_count),
                "last_run": dict(self._last_run),
            }

    # ── Internal helpers ──

    def _register_defaults(self) -> None:
        """Register the default no-op periodic tasks."""
        for name, interval in self.DEFAULT_TASKS:
            self.add_task(name, self._noop_task, interval)

    @staticmethod
    async def _noop_task() -> None:
        """Default no-op task body."""
        return None

    async def _run_loop(self, name: str, spec: Dict[str, Any]) -> None:
        interval = float(spec.get("interval", 5.0))
        try:
            while self._running:
                start = time.monotonic()
                try:
                    await self._invoke(name, spec["fn"])
                except Exception as exc:
                    logger.warning(
                        "Scheduled task '%s' failed: %s", name, exc
                    )
                    with self._lock:
                        self._failure_count[name] = (
                            self._failure_count.get(name, 0) + 1
                        )
                elapsed = time.monotonic() - start
                sleep_for = max(interval - elapsed, 0.05)
                await asyncio.sleep(sleep_for)
        except asyncio.CancelledError:
            logger.debug("Task loop '%s' cancelled.", name)
            raise
        except Exception:
            logger.exception("Task loop '%s' crashed.", name)

    async def _invoke(self, name: str, fn: Callable) -> Any:
        with self._lock:
            self._exec_count[name] = self._exec_count.get(name, 0) + 1
            self._last_run[name] = time.time()
        result = fn()
        if inspect.isawaitable(result):
            result = await result
        return result

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"HealthScheduler(running={self._running}, "
                f"tasks={len(self._tasks)})"
            )
