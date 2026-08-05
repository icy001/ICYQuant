"""Graceful shutdown manager for ICYQuant service discovery.

Provides ``GracefulShutdownManager`` for coordinated shutdown
of all platform components with proper ordering and timeout
protection.
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


class ShutdownPhase:
    """A phase in the graceful shutdown sequence."""

    def __init__(
        self,
        name: str,
        callback: Callable,
        timeout_s: float = 10.0,
    ) -> None:
        self.name = name
        self.callback = callback
        self.timeout_s = timeout_s
        self.completed = False
        self.success = False
        self.error: Optional[str] = None
        self.duration_s = 0.0


class GracefulShutdownManager:
    """Coordinates graceful platform shutdown.

    Executes shutdown phases in reverse order with timeout
    protection, ensuring each component has time to finish
    in-flight operations before shutdown.
    """

    def __init__(
        self, context: Optional[DiscoveryContext] = None
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._phases: List[ShutdownPhase] = []
        self._running = False
        self._shutdown_count = 0
        self._last_shutdown: Optional[Dict[str, Any]] = None
        self._default_phases: List[ShutdownPhase] = []
        self._register_defaults()

    def _register_defaults(self) -> None:
        self._default_phases = [
            ShutdownPhase(
                "gateway",
                self._shutdown_gateway,
                timeout_s=5.0,
            ),
            ShutdownPhase(
                "scheduler",
                self._shutdown_scheduler,
                timeout_s=5.0,
            ),
            ShutdownPhase(
                "persist_snapshot",
                self._persist_snapshot,
                timeout_s=15.0,
            ),
            ShutdownPhase(
                "flush_events",
                self._flush_events,
                timeout_s=10.0,
            ),
            ShutdownPhase(
                "synchronizer",
                self._shutdown_synchronizer,
                timeout_s=5.0,
            ),
            ShutdownPhase(
                "heartbeat",
                self._shutdown_heartbeat,
                timeout_s=10.0,
            ),
            ShutdownPhase(
                "resolver",
                self._shutdown_resolver,
                timeout_s=5.0,
            ),
            ShutdownPhase(
                "registry",
                self._shutdown_registry,
                timeout_s=10.0,
            ),
        ]

    def add_phase(
        self,
        name: str,
        callback: Callable,
        timeout_s: float = 10.0,
    ) -> None:
        """Add a custom shutdown phase.

        Args:
            name: Phase name.
            callback: Shutdown callback.
            timeout_s: Phase timeout in seconds.
        """
        with self._lock:
            self._phases.append(
                ShutdownPhase(name, callback, timeout_s)
            )
        logger.info(
            "Custom shutdown phase '%s' added.", name
        )

    async def shutdown(
        self, timeout_s: float = 30.0
    ) -> Dict[str, Any]:
        """Execute graceful platform shutdown.

        Args:
            timeout_s: Overall shutdown timeout.

        Returns:
            Shutdown result.
        """
        with self._lock:
            if self._running:
                return {
                    "success": False,
                    "error": "Shutdown already in progress",
                }
            self._running = True
            self._shutdown_count += 1

        all_phases = self._default_phases + self._phases
        results: List[Dict[str, Any]] = []
        start = time.monotonic()

        for phase in all_phases:
            if time.monotonic() - start > timeout_s:
                phase.success = False
                phase.error = "Global timeout"
                results.append(self._phase_result(phase))
                continue

            phase_start = time.monotonic()
            try:
                coro = phase.callback()
                if asyncio.iscoroutine(coro):
                    result = await asyncio.wait_for(
                        coro, timeout=phase.timeout_s
                    )
                else:
                    result = coro
                phase.success = True
                phase.duration_s = (
                    time.monotonic() - phase_start
                )
                results.append(
                    self._phase_result(phase, result)
                )
            except asyncio.TimeoutError:
                phase.success = False
                phase.error = "Timeout"
                phase.duration_s = (
                    time.monotonic() - phase_start
                )
                results.append(self._phase_result(phase))
                logger.warning(
                    "Shutdown phase '%s' timed out.",
                    phase.name,
                )
            except Exception as exc:
                phase.success = False
                phase.error = str(exc)
                phase.duration_s = (
                    time.monotonic() - phase_start
                )
                results.append(self._phase_result(phase))
                logger.warning(
                    "Shutdown phase '%s' failed: %s",
                    phase.name,
                    exc,
                )

        total_duration = time.monotonic() - start
        all_successful = all(
            r.get("success", False) for r in results
        )

        result: Dict[str, Any] = {
            "success": all_successful,
            "phases": results,
            "total_phases": len(all_phases),
            "successful_phases": sum(
                1 for r in results if r.get("success")
            ),
            "failed_phases": sum(
                1 for r in results if not r.get("success")
            ),
            "duration_s": total_duration,
            "timestamp": datetime.utcnow().isoformat(),
        }

        with self._lock:
            self._running = False
            self._last_shutdown = result

        logger.info(
            "Graceful shutdown completed: %d/%d phases in %.3fs.",
            result["successful_phases"],
            result["total_phases"],
            total_duration,
        )
        return result

    def _phase_result(
        self,
        phase: ShutdownPhase,
        result: Any = None,
    ) -> Dict[str, Any]:
        return {
            "name": phase.name,
            "success": phase.success,
            "duration_s": phase.duration_s,
            "error": phase.error,
            "result": str(result)[:200] if result else None,
        }

    async def _shutdown_gateway(self) -> Any:
        gateway = self._context.get("gateway")
        if gateway:
            shutdown_fn = getattr(gateway, "shutdown", None)
            if callable(shutdown_fn):
                coro = shutdown_fn()
                if asyncio.iscoroutine(coro):
                    return await coro
        return True

    async def _shutdown_scheduler(self) -> Any:
        scheduler = self._context.get("scheduler")
        if scheduler:
            stop_fn = getattr(scheduler, "stop", None)
            if callable(stop_fn):
                coro = stop_fn()
                if asyncio.iscoroutine(coro):
                    return await coro
        return True

    async def _persist_snapshot(self) -> Any:
        """Persist latest platform snapshot before shutdown.

        Ensures no leases, topology state, or configuration
        is lost during shutdown.
        """
        snapshot = self._context.get("snapshot")
        if snapshot:
            export_fn = getattr(snapshot, "export", None)
            if callable(export_fn):
                coro = export_fn()
                if asyncio.iscoroutine(coro):
                    result = await coro
                    logger.info(
                        "Snapshot persisted before shutdown."
                    )
                    return result
        return True

    async def _flush_events(self) -> Any:
        """Flush pending events before shutdown.

        Ensures no events are lost during shutdown by
        draining the event bus and publisher queues.
        """
        eventbus = self._context.get("eventbus")
        if eventbus:
            flush_fn = getattr(eventbus, "flush", None)
            if callable(flush_fn):
                coro = flush_fn()
                if asyncio.iscoroutine(coro):
                    result = await coro
                    logger.info("Events flushed before shutdown.")
                    return result

        publisher = self._context.get("publisher")
        if publisher:
            flush_fn = getattr(publisher, "flush", None)
            if callable(flush_fn):
                coro = flush_fn()
                if asyncio.iscoroutine(coro):
                    result = await coro
                    logger.info("Publisher events flushed.")
                    return result

        logger.info("No events to flush during shutdown.")
        return True

    async def _shutdown_synchronizer(self) -> Any:
        sync = self._context.get("synchronizer")
        if sync:
            stop_fn = getattr(sync, "stop_auto_sync", None)
            if callable(stop_fn):
                coro = stop_fn()
                if asyncio.iscoroutine(coro):
                    return await coro
        return True

    async def _shutdown_heartbeat(self) -> Any:
        hb = self._context.get("heartbeat")
        if hb:
            stop_fn = getattr(hb, "stop", None)
            if callable(stop_fn):
                coro = stop_fn()
                if asyncio.iscoroutine(coro):
                    return await coro
        return True

    async def _shutdown_resolver(self) -> Any:
        resolver = self._context.get("resolver")
        if resolver:
            shutdown_fn = getattr(resolver, "shutdown", None)
            if callable(shutdown_fn):
                coro = shutdown_fn()
                if asyncio.iscoroutine(coro):
                    return await coro
        return True

    async def _shutdown_registry(self) -> Any:
        registry = self._context.get("registry")
        if registry:
            shutdown_fn = getattr(registry, "shutdown", None)
            if callable(shutdown_fn):
                coro = shutdown_fn()
                if asyncio.iscoroutine(coro):
                    return await coro
        return True

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "shutdown_count": self._shutdown_count,
                "default_phases": [
                    p.name for p in self._default_phases
                ],
                "custom_phases": [
                    p.name for p in self._phases
                ],
                "last_shutdown": self._last_shutdown,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"GracefulShutdownManager("
                f"shutdowns={self._shutdown_count})"
            )
