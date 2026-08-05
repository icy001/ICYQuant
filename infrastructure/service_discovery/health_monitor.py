"""Health monitor for ICYQuant service discovery.

Provides ``HealthMonitor`` for running background health checks
against registered service instances. Maintains per-instance health
state and exposes aggregate health views. Thread-safe.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .exceptions import ServiceDiscoveryError
from .health_checker import HealthChecker

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Background health monitor for service instances.

    Periodically runs health probes against monitored instances and
    records the latest health state per instance.

    Args:
        health_checker: Optional ``HealthChecker`` instance. A default
            one is created if not supplied.
    """

    def __init__(self, health_checker: Optional[HealthChecker] = None) -> None:
        self._health_checker = health_checker or HealthChecker()
        self._lock = threading.RLock()
        self._monitored: Dict[str, Dict[str, Any]] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._total_checks = 0
        self._total_failures = 0

    # ── Helpers ──

    @staticmethod
    def _make_key(service_name: str, instance_id: str) -> str:
        return f"{service_name}:{instance_id}"

    # ── Public API ──

    async def start(self) -> None:
        """Start the health monitor.

        Raises:
            ServiceDiscoveryError: If already running.
        """
        with self._lock:
            if self._running:
                raise ServiceDiscoveryError(
                    "HealthMonitor is already running."
                )
            self._running = True
        logger.info("HealthMonitor started.")

    async def stop(self) -> None:
        """Stop the health monitor and cancel all monitoring tasks."""
        with self._lock:
            self._running = False
            tasks = list(self._tasks.values())
            self._tasks.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("HealthMonitor stopped.")

    async def monitor(
        self,
        service_name: str,
        instance_id: str,
        probe_type: str = "tcp",
        interval: float = 10.0,
    ) -> None:
        """Begin monitoring an instance.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
            probe_type: Probe type to use for checks.
            interval: Monitoring interval in seconds.
        """
        key = self._make_key(service_name, instance_id)
        effective_interval = float(interval) if interval > 0 else 10.0
        with self._lock:
            existing = self._monitored.get(key)
            if existing and existing.get("monitoring"):
                logger.debug(
                    "Already monitoring '%s'.", key
                )
                return
            record = existing or {
                "service_name": service_name,
                "instance_id": instance_id,
            }
            record.update(
                {
                    "probe_type": probe_type,
                    "interval": effective_interval,
                    "monitoring": True,
                    "last_check": None,
                    "last_check_ts": 0.0,
                    "healthy": True,
                    "consecutive_failures": 0,
                    "check_count": 0,
                    "error": None,
                }
            )
            self._monitored[key] = record
        task = asyncio.create_task(
            self._monitor_loop(service_name, instance_id, probe_type, effective_interval)
        )
        with self._lock:
            self._tasks[key] = task
        logger.info(
            "Started monitoring '%s/%s' (probe=%s, interval=%.2fs).",
            service_name,
            instance_id,
            probe_type,
            effective_interval,
        )

    def unmonitor(self, service_name: str, instance_id: str) -> None:
        """Stop monitoring an instance."""
        key = self._make_key(service_name, instance_id)
        with self._lock:
            record = self._monitored.get(key)
            if record is not None:
                record["monitoring"] = False
            task = self._tasks.pop(key, None)
        if task is not None and not task.done():
            task.cancel()
        logger.info(
            "Stopped monitoring '%s/%s'.", service_name, instance_id
        )

    def get_health(
        self, service_name: str, instance_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return the latest health state for an instance."""
        key = self._make_key(service_name, instance_id)
        with self._lock:
            record = self._monitored.get(key)
            if record is None:
                return None
            return dict(record)

    def get_all_health(self) -> Dict[str, Dict[str, Any]]:
        """Return the latest health state for all monitored instances."""
        with self._lock:
            return {k: dict(v) for k, v in self._monitored.items()}

    def is_healthy(self, service_name: str, instance_id: str) -> bool:
        """Return whether an instance is currently healthy."""
        key = self._make_key(service_name, instance_id)
        with self._lock:
            record = self._monitored.get(key)
            return bool(record and record.get("healthy"))

    def get_unhealthy(self) -> List[Dict[str, Any]]:
        """Return a list of all currently unhealthy instances."""
        with self._lock:
            return [
                dict(r)
                for r in self._monitored.values()
                if not r.get("healthy")
            ]

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the health monitor."""
        with self._lock:
            healthy = sum(
                1 for r in self._monitored.values() if r.get("healthy")
            )
            unhealthy = len(self._monitored) - healthy
            return {
                "running": self._running,
                "monitored_count": len(self._monitored),
                "healthy_count": healthy,
                "unhealthy_count": unhealthy,
                "total_checks": self._total_checks,
                "total_failures": self._total_failures,
            }

    # ── Monitoring loop ──

    async def _monitor_loop(
        self,
        service_name: str,
        instance_id: str,
        probe_type: str,
        interval: float,
    ) -> None:
        key = self._make_key(service_name, instance_id)
        try:
            while self._is_monitoring(key):
                try:
                    result = await self._health_checker.check(
                        service_name, instance_id, probe_type=probe_type
                    )
                except Exception as exc:
                    self._record_check(key, False, error=str(exc))
                else:
                    inner = result.get("result", {})
                    self._record_check(
                        key,
                        bool(inner.get("success")),
                        result=result,
                    )
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.debug("Monitor loop cancelled for '%s'.", key)
            raise
        except Exception:
            logger.exception("Monitor loop crashed for '%s'.", key)

    def _is_monitoring(self, key: str) -> bool:
        with self._lock:
            record = self._monitored.get(key)
            return bool(
                self._running
                and record
                and record.get("monitoring")
            )

    def _record_check(
        self,
        key: str,
        success: bool,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow()
        now_ts = time.time()
        with self._lock:
            record = self._monitored.get(key)
            if record is None:
                return
            record["last_check"] = now.isoformat()
            record["last_check_ts"] = now_ts
            record["check_count"] = int(record.get("check_count", 0)) + 1
            self._total_checks += 1
            if success:
                record["healthy"] = True
                record["consecutive_failures"] = 0
                record["error"] = None
            else:
                record["healthy"] = False
                record["consecutive_failures"] = (
                    int(record.get("consecutive_failures", 0)) + 1
                )
                record["error"] = error or "health check failed"
                self._total_failures += 1
            if result is not None:
                record["last_result"] = result

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"HealthMonitor(running={self._running}, "
                f"monitored={len(self._monitored)})"
            )
