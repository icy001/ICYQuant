"""Heartbeat scheduler for ICYQuant service discovery.

Provides ``HeartbeatScheduler`` for periodically dispatching
heartbeats for registered service instances using asyncio tasks.
Supports jitter (±10% of the configured interval) to avoid the
thundering herd problem.
"""

from __future__ import annotations

import asyncio
import logging
import random
import threading
import time
from typing import Any, Dict, List, Optional

from .exceptions import ServiceDiscoveryError
from .heartbeat import HeartbeatService

logger = logging.getLogger(__name__)


class HeartbeatScheduler:
    """Schedules periodic heartbeats for registered instances.

    Uses ``asyncio.create_task`` to dispatch heartbeats at the
    configured interval with ±10% jitter. Thread-safe via a
    reentrant lock; the scheduler loop itself runs in the asyncio
    event loop.

    Args:
        heartbeat_service: The ``HeartbeatService`` used to send beats.
    """

    JITTER_FACTOR = 0.1

    def __init__(self, heartbeat_service: Optional[HeartbeatService] = None) -> None:
        self._heartbeat_service = heartbeat_service
        self._lock = threading.RLock()
        self._registrations: Dict[str, Dict[str, Any]] = {}
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._wake: Optional[asyncio.Event] = None
        self._dispatch_count = 0
        self._failure_count = 0

    # ── Helpers ──

    @staticmethod
    def _make_key(service_name: str, instance_id: str) -> str:
        return f"{service_name}:{instance_id}"

    def _apply_jitter(self, interval: float) -> float:
        """Return ``interval`` with ±10% random jitter applied."""
        if interval <= 0:
            return interval
        delta = interval * self.JITTER_FACTOR
        return max(interval + random.uniform(-delta, delta), 0.1)

    # ── Public API ──

    async def start(self) -> None:
        """Start the scheduler loop.

        Raises:
            ServiceDiscoveryError: If the scheduler is already running.
        """
        with self._lock:
            if self._running:
                raise ServiceDiscoveryError(
                    "HeartbeatScheduler is already running."
                )
            self._running = True
            self._wake = asyncio.Event()
        self._task = asyncio.create_task(self._run())
        logger.info("HeartbeatScheduler started.")

    async def stop(self) -> None:
        """Stop the scheduler loop gracefully."""
        with self._lock:
            self._running = False
            wake = self._wake
        if wake is not None:
            wake.set()
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("HeartbeatScheduler stopped.")

    def register(
        self,
        service_name: str,
        instance_id: str,
        interval: float = 5.0,
    ) -> None:
        """Register an instance for scheduled heartbeats.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
            interval: Heartbeat interval in seconds.
        """
        key = self._make_key(service_name, instance_id)
        effective_interval = float(interval) if interval > 0 else 5.0
        with self._lock:
            self._registrations[key] = {
                "service_name": service_name,
                "instance_id": instance_id,
                "interval": effective_interval,
                "next_run": time.monotonic() + self._apply_jitter(
                    effective_interval
                ),
                "last_run": 0.0,
                "dispatch_count": 0,
                "failure_count": 0,
            }
        logger.info(
            "Registered '%s/%s' with HeartbeatScheduler (interval=%.2fs).",
            service_name,
            instance_id,
            effective_interval,
        )
        if self._wake is not None:
            self._wake.set()

    def unregister(self, service_name: str, instance_id: str) -> None:
        """Unregister an instance from scheduled heartbeats."""
        key = self._make_key(service_name, instance_id)
        with self._lock:
            self._registrations.pop(key, None)
        logger.info(
            "Unregistered '%s/%s' from HeartbeatScheduler.",
            service_name,
            instance_id,
        )

    def is_running(self) -> bool:
        """Return whether the scheduler loop is currently running."""
        with self._lock:
            return self._running

    def get_registered(self) -> List[Dict[str, Any]]:
        """Return a list of registered heartbeat targets."""
        with self._lock:
            return [dict(r) for r in self._registrations.values()]

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the scheduler."""
        with self._lock:
            return {
                "running": self._running,
                "registered_count": len(self._registrations),
                "dispatch_count": self._dispatch_count,
                "failure_count": self._failure_count,
                "heartbeat_service_attached": self._heartbeat_service is not None,
            }

    # ── Scheduler loop ──

    async def _run(self) -> None:
        """Main scheduler loop dispatching heartbeats."""
        assert self._wake is not None
        try:
            while self._running:
                now = time.monotonic()
                due = self._due_targets(now)
                if due:
                    await asyncio.gather(
                        *(self._dispatch(target) for target in due),
                        return_exceptions=True,
                    )
                sleep_for = self._next_sleep(now)
                self._wake.clear()
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=sleep_for)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            logger.debug("HeartbeatScheduler loop cancelled.")
            raise
        except Exception:
            logger.exception("HeartbeatScheduler loop crashed.")
            raise

    def _due_targets(self, now: float) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                dict(r)
                for r in self._registrations.values()
                if r.get("next_run", 0.0) <= now
            ]

    def _next_sleep(self, now: float) -> float:
        with self._lock:
            upcoming = [
                r.get("next_run", now)
                for r in self._registrations.values()
                if r.get("next_run", now) > now
            ]
        if not upcoming:
            return 0.5
        return max(min(upcoming) - now, 0.05)

    async def _dispatch(self, target: Dict[str, Any]) -> None:
        service_name = target["service_name"]
        instance_id = target["instance_id"]
        interval = float(target.get("interval", 5.0))
        key = self._make_key(service_name, instance_id)
        try:
            if self._heartbeat_service is not None:
                await self._heartbeat_service.beat(service_name, instance_id)
            with self._lock:
                record = self._registrations.get(key)
                if record is not None:
                    record["last_run"] = time.monotonic()
                    record["dispatch_count"] = int(
                        record.get("dispatch_count", 0)
                    ) + 1
                    record["next_run"] = record["last_run"] + self._apply_jitter(
                        interval
                    )
                self._dispatch_count += 1
        except Exception as exc:
            with self._lock:
                record = self._registrations.get(key)
                if record is not None:
                    record["failure_count"] = int(
                        record.get("failure_count", 0)
                    ) + 1
                    record["next_run"] = time.monotonic() + self._apply_jitter(
                        interval
                    )
                self._failure_count += 1
            logger.warning(
                "Scheduled heartbeat for '%s/%s' failed: %s",
                service_name,
                instance_id,
                exc,
            )

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"HeartbeatScheduler(running={self._running}, "
                f"registered={len(self._registrations)})"
            )
