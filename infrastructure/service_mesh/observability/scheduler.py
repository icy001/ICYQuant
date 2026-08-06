"""Scheduler for ICYQuant Service Mesh observability.

Provides ``ObservabilityScheduler`` for background tasks including
policy refresh, metrics flush, trace cleanup, SLO evaluation,
and anomaly scanning.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ObservabilityTask:
    """A scheduled observability task."""

    name: str
    fn: Callable
    interval_s: float = 300.0
    enabled: bool = True
    last_run: Optional[float] = None
    run_count: int = 0
    error_count: int = 0
    last_result: Optional[Any] = None
    last_error: Optional[str] = None

    def should_run(self, now: float) -> bool:
        if not self.enabled:
            return False
        if self.last_run is None:
            return True
        return now - self.last_run >= self.interval_s


class ObservabilityScheduler:
    """Runs background observability tasks."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tasks: Dict[str, ObservabilityTask] = {}
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register_task(
            "policy_refresh",
            lambda: None,
            interval_s=300.0,
            enabled=False,
        )
        self.register_task(
            "metrics_flush",
            lambda: None,
            interval_s=60.0,
            enabled=False,
        )
        self.register_task(
            "trace_cleanup",
            lambda: None,
            interval_s=600.0,
            enabled=False,
        )
        self.register_task(
            "slo_evaluation",
            lambda: None,
            interval_s=120.0,
            enabled=False,
        )
        self.register_task(
            "anomaly_scan",
            lambda: None,
            interval_s=60.0,
            enabled=False,
        )

    @property
    def is_running(self) -> bool:
        return self._running

    def register_task(
        self,
        name: str,
        fn: Callable,
        interval_s: float = 300.0,
        enabled: bool = True,
    ) -> None:
        with self._lock:
            self._tasks[name] = ObservabilityTask(
                name=name,
                fn=fn,
                interval_s=interval_s,
                enabled=enabled,
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
                "tasks": [
                    {
                        "name": t.name,
                        "enabled": t.enabled,
                        "interval_s": t.interval_s,
                        "run_count": t.run_count,
                        "error_count": t.error_count,
                    }
                    for t in self._tasks.values()
                ],
            }

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._loop = asyncio.get_event_loop()
        self._loop.create_task(self._run_loop())
        logger.info("Observability scheduler started")

    async def stop(self) -> None:
        self._running = False
        logger.info("Observability scheduler stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                now = time.monotonic()
                with self._lock:
                    tasks = list(self._tasks.values())
                for task in tasks:
                    if task.should_run(now):
                        await self._run_task(task)
            except Exception as exc:
                logger.error("Scheduler loop error: %s", exc)
            await asyncio.sleep(1.0)

    async def _run_task(self, task: ObservabilityTask) -> None:
        try:
            result = task.fn()
            if asyncio.iscoroutine(result):
                result = await asyncio.wait_for(result, timeout=30.0)
            task.last_run = time.monotonic()
            task.run_count += 1
            task.last_result = result
            task.last_error = None
        except Exception as exc:
            task.error_count += 1
            task.last_error = str(exc)
            logger.warning("Task '%s' failed: %s", task.name, exc)

    async def run_task_now(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            task = self._tasks.get(name)
        if not task:
            return None
        await self._run_task(task)
        return self.get_task_status(name)
