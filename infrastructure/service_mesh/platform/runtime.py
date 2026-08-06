"""Mesh Platform Runtime for the Service Mesh Platform.

Provides ``MeshPlatformRuntime`` for dynamic reload, hot configuration,
policy refresh, runtime recovery, and background task management
at the platform level.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics

logger = logging.getLogger(__name__)


class MeshPlatformRuntime:
    """Platform-level runtime manager for the service mesh."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._reload_handlers: Dict[str, Callable] = {}
        self._config: Dict[str, Any] = {}
        self._background_tasks: List[asyncio.Task] = []
        self._scheduler_tasks: Dict[str, asyncio.Task] = {}
        self._reload_count = 0
        self._running = False
        self._start_time: Optional[float] = None
        self._recovery_count = 0
        self._max_recovery_attempts = 5

    async def initialize(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Initialize the platform runtime."""
        with self._lock:
            self._running = True
            self._start_time = time.monotonic()
            if config:
                self._config = config

        self._metrics.increment_runtime_total()
        self._telemetry.log_runtime(
            "initialize", "completed",
            {"config_keys": list(self._config.keys())},
        )
        logger.info("Platform runtime initialized.")
        return {"success": True, "runtime": "initialized"}

    @property
    def is_running(self) -> bool:
        return self._running

    async def reload(
        self,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Hot-reload platform runtime configuration."""
        with self._lock:
            self._reload_count += 1

        if config:
            with self._lock:
                self._config.update(config)

        results: Dict[str, Any] = {}
        for name, handler in self._reload_handlers.items():
            try:
                result = handler(config)
                if asyncio.iscoroutine(result):
                    result = await result
                results[name] = {"success": True, "result": result}
            except Exception as exc:
                results[name] = {"success": False, "error": str(exc)}

        self._metrics.record_timer(
            "runtime_reload",
            time.monotonic() - (self._start_time or time.monotonic()),
        )

        self._telemetry.log_runtime(
            "reload", "completed",
            {"reload_count": self._reload_count},
        )

        logger.info(
            "Platform runtime reloaded (count=%d).",
            self._reload_count,
        )
        return {
            "success": True,
            "reload_count": self._reload_count,
            "handler_results": results,
        }

    async def stop(self) -> Dict[str, Any]:
        """Stop the platform runtime."""
        with self._lock:
            self._running = False

        # Cancel scheduler tasks
        for name, task in self._scheduler_tasks.items():
            if not task.done():
                task.cancel()
        self._scheduler_tasks.clear()

        # Cancel background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(
            *self._background_tasks,
            return_exceptions=True,
        )
        self._background_tasks.clear()

        self._telemetry.log_runtime("stop", "completed")
        logger.info("Platform runtime stopped.")
        return {"success": True, "runtime": "stopped"}

    async def recover(
        self,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Attempt runtime recovery after failure."""
        if self._recovery_count >= self._max_recovery_attempts:
            return {
                "success": False,
                "error": "Max recovery attempts exceeded",
                "recovery_count": self._recovery_count,
            }

        self._recovery_count += 1

        # Stop and reinitialize
        await self.stop()
        result = await self.initialize(config)

        self._telemetry.log_runtime(
            "recover", "completed",
            {"recovery_count": self._recovery_count},
        )
        logger.warning(
            "Platform runtime recovered (attempt=%d).",
            self._recovery_count,
        )
        return result

    def register_reload_handler(
        self,
        name: str,
        handler: Callable,
    ) -> None:
        self._reload_handlers[name] = handler

    async def refresh_policies(
        self, policies: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Refresh platform policies."""
        if policies:
            with self._lock:
                self._config["policies"] = policies
        return {"success": True, "policies_refreshed": bool(policies)}

    def add_background_task(
        self, coro_func: Callable, *args, **kwargs
    ) -> asyncio.Task:
        task = asyncio.create_task(coro_func(*args, **kwargs))
        with self._lock:
            self._background_tasks.append(task)
        return task

    def add_scheduler_task(
        self,
        name: str,
        coro_func: Callable,
        interval_s: float,
        *args,
        **kwargs,
    ) -> None:
        """Add a periodic scheduler task."""

        async def _run_periodic():
            while self._running:
                try:
                    await coro_func(*args, **kwargs)
                except Exception as exc:
                    logger.warning(
                        "Scheduler task '%s' failed: %s",
                        name,
                        exc,
                    )
                await asyncio.sleep(interval_s)

        task = asyncio.create_task(_run_periodic())
        with self._lock:
            self._scheduler_tasks[name] = task

    def remove_scheduler_task(self, name: str) -> None:
        with self._lock:
            task = self._scheduler_tasks.pop(name, None)
            if task and not task.done():
                task.cancel()

    async def cancel_all_tasks(self) -> None:
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(
            *self._background_tasks,
            return_exceptions=True,
        )
        self._background_tasks.clear()

    def get_config(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._config)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "reload_count": self._reload_count,
                "recovery_count": self._recovery_count,
                "config_keys": list(self._config.keys()),
                "background_tasks": len(self._background_tasks),
                "scheduler_tasks": list(self._scheduler_tasks.keys()),
                "reload_handlers": list(self._reload_handlers.keys()),
                "uptime_s": (
                    time.monotonic() - self._start_time
                    if self._start_time
                    else 0
                ),
            }

    def clear(self) -> None:
        with self._lock:
            self._config.clear()
            self._reload_handlers.clear()
            self._reload_count = 0
            self._recovery_count = 0

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"MeshPlatformRuntime(running={self._running}, "
                f"reloads={self._reload_count})"
            )
