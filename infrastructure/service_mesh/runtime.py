"""Mesh runtime for the Service Mesh.

Provides ``MeshRuntime`` for dynamic reload, hot configuration,
policy refresh, and background task management.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .context import MeshContext
from .events import MeshEvent, MeshEventPublisher

logger = logging.getLogger(__name__)


class MeshRuntime:
    """Runtime manager for the service mesh."""

    def __init__(
        self,
        context: Optional[MeshContext] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or MeshContext()
        self._publisher: Optional[MeshEventPublisher] = None
        self._reload_handlers: Dict[str, Callable] = {}
        self._config: Dict[str, Any] = {}
        self._background_tasks: List[asyncio.Task] = []
        self._reload_count = 0
        self._running = False
        self._start_time: Optional[float] = None

        self._context.register("runtime", self)

    def set_publisher(self, publisher: MeshEventPublisher) -> None:
        self._publisher = publisher

    async def start(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        with self._lock:
            self._running = True
            self._start_time = time.monotonic()
            if config:
                self._config = config

        if self._publisher:
            await self._publisher.publish(MeshEvent.MESH_STARTED)

        logger.info("Mesh runtime started.")
        return {"success": True, "runtime": "started"}

    async def stop(self) -> Dict[str, Any]:
        with self._lock:
            self._running = False

        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(
            *self._background_tasks,
            return_exceptions=True,
        )
        self._background_tasks.clear()

        if self._publisher:
            await self._publisher.publish(MeshEvent.MESH_STOPPED)

        logger.info("Mesh runtime stopped.")
        return {"success": True, "runtime": "stopped"}

    @property
    def is_running(self) -> bool:
        return self._running

    async def reload(
        self,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Hot-reload runtime configuration."""
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

        if self._publisher:
            await self._publisher.publish(
                MeshEvent.MESH_RELOADED,
                {"reload_count": self._reload_count},
            )

        logger.info(
            "Mesh runtime reloaded (count=%d).",
            self._reload_count,
        )
        return {
            "success": True,
            "reload_count": self._reload_count,
            "handler_results": results,
        }

    def register_reload_handler(
        self,
        name: str,
        handler: Callable,
    ) -> None:
        self._reload_handlers[name] = handler

    async def refresh_policies(
        self, policies: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Refresh mesh policies."""
        if policies:
            with self._lock:
                self._config["policies"] = policies
        return {"success": True, "policies_refreshed": bool(policies)}

    def add_background_task(
        self, coro_func: Callable, *args, **kwargs
    ) -> asyncio.Task:
        """Add a background task to the runtime."""
        task = asyncio.create_task(coro_func(*args, **kwargs))
        with self._lock:
            self._background_tasks.append(task)
        return task

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
                "config_keys": list(self._config.keys()),
                "background_tasks": len(self._background_tasks),
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

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"MeshRuntime(running={self._running}, "
                f"reloads={self._reload_count})"
            )
