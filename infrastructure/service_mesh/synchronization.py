"""Mesh Synchronization for the Service Mesh.

Provides ``MeshSynchronizer`` for synchronizing configuration
between the control plane, event bus, cluster nodes, and
sidecar proxies, ensuring consistent configuration and
real-time updates.
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


class MeshSynchronizer:
    """Synchronizes configuration across mesh components."""

    def __init__(
        self,
        context: Optional[MeshContext] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or MeshContext()
        self._publisher: Optional[MeshEventPublisher] = None
        self._sync_handlers: Dict[str, Callable] = {}
        self._last_sync: Optional[Dict[str, Any]] = None
        self._sync_count = 0
        self._running = False
        self._sync_task: Optional[asyncio.Task] = None

        self._context.register("synchronizer", self)

    def set_publisher(self, publisher: MeshEventPublisher) -> None:
        self._publisher = publisher

    async def start_auto_sync(
        self, interval_s: float = 30.0
    ) -> None:
        """Start automatic periodic synchronization."""
        if self._running:
            return

        self._running = True
        self._sync_task = asyncio.create_task(
            self._auto_sync_loop(interval_s)
        )
        logger.info(
            "Auto sync started (interval=%.1fs).", interval_s
        )

    async def stop_auto_sync(self) -> None:
        """Stop automatic synchronization."""
        self._running = False
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        self._sync_task = None
        logger.info("Auto sync stopped.")

    async def _auto_sync_loop(self, interval_s: float) -> None:
        while self._running:
            try:
                await self.synchronize()
            except Exception as exc:
                logger.warning("Auto sync failed: %s", exc)
            await asyncio.sleep(interval_s)

    async def synchronize(
        self,
        component: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute mesh synchronization."""
        with self._lock:
            self._sync_count += 1

        results: Dict[str, Any] = {}
        components_to_sync = (
            [component] if component else list(self._sync_handlers.keys())
        )

        for comp in components_to_sync:
            handler = self._sync_handlers.get(comp)
            if handler:
                try:
                    result = handler()
                    if asyncio.iscoroutine(result):
                        result = await result
                    results[comp] = {
                        "success": True,
                        "result": result,
                    }
                except Exception as exc:
                    results[comp] = {
                        "success": False,
                        "error": str(exc),
                    }

        sync_result = {
            "sync_id": self._sync_count,
            "timestamp": datetime.utcnow().isoformat(),
            "components": results,
            "all_successful": all(
                r.get("success", False)
                for r in results.values()
            ),
        }

        with self._lock:
            self._last_sync = sync_result

        if self._publisher:
            await self._publisher.publish(
                MeshEvent.SYNC_COMPLETED,
                {"sync_id": self._sync_count},
            )

        logger.info(
            "Synchronization #%d completed: %d components.",
            self._sync_count,
            len(results),
        )
        return sync_result

    def register_sync_handler(
        self,
        component: str,
        handler: Callable,
    ) -> None:
        self._sync_handlers[component] = handler

    def unregister_sync_handler(self, component: str) -> bool:
        if component in self._sync_handlers:
            del self._sync_handlers[component]
            return True
        return False

    async def sync_configuration(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Push configuration to all registered handlers."""
        results: Dict[str, Any] = {}
        for name, handler in self._sync_handlers.items():
            try:
                result = handler(config)
                if asyncio.iscoroutine(result):
                    result = await result
                results[name] = {"success": True}
            except Exception as exc:
                results[name] = {
                    "success": False,
                    "error": str(exc),
                }

        return {
            "success": all(
                r.get("success", False)
                for r in results.values()
            ),
            "component_results": results,
        }

    @property
    def is_running(self) -> bool:
        return self._running

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "sync_count": self._sync_count,
                "registered_handlers": list(
                    self._sync_handlers.keys()
                ),
                "last_sync": self._last_sync,
            }

    def clear(self) -> None:
        with self._lock:
            self._sync_handlers.clear()
            self._sync_count = 0
            self._last_sync = None

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"MeshSynchronizer(running={self._running}, "
                f"syncs={self._sync_count})"
            )
