"""
Connection Health Monitor — Monitors the health of all active connections
with configurable thresholds, degradation detection, and alerting.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ConnectionHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ConnectionHealthRecord:
    connection_id: str
    exchange_id: str
    health: ConnectionHealth = ConnectionHealth.UNKNOWN
    last_checked: Optional[datetime] = None
    last_error: str = ""
    consecutive_failures: int = 0
    latency_ms: float = 0.0
    message_rate_per_second: float = 0.0
    error_rate: float = 0.0
    uptime_seconds: float = 0.0


class ConnectionHealthMonitor:
    """
    Monitors the health of all active transport connections.

    Tracks latency, error rates, message throughput, and performs
    periodic health checks with configurable thresholds.

    Usage::

        monitor = ConnectionHealthMonitor()
        await monitor.initialize()
        await monitor.register("conn_001", "binance")
        health = await monitor.check("conn_001")
    """

    def __init__(
        self,
        health_check_interval: float = 15.0,
        unhealthy_threshold: int = 3,
        latency_warning_ms: float = 1000.0,
        latency_critical_ms: float = 5000.0,
    ) -> None:
        self.health_check_interval = health_check_interval
        self.unhealthy_threshold = unhealthy_threshold
        self.latency_warning_ms = latency_warning_ms
        self.latency_critical_ms = latency_critical_ms
        self._records: dict[str, ConnectionHealthRecord] = {}
        self._alert_callbacks: list[Callable] = []
        self._health_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the health monitor."""
        logger.info("ConnectionHealthMonitor initialized.")

    async def start(self) -> None:
        """Start periodic health checks."""
        if self.health_check_interval > 0:
            self._health_task = asyncio.create_task(self._health_check_loop())

    async def stop(self) -> None:
        """Stop health monitoring."""
        if self._health_task:
            self._health_task.cancel()
        logger.info("ConnectionHealthMonitor stopped.")

    def on_alert(self, callback: Callable) -> None:
        """Register an alert callback for health status changes."""
        self._alert_callbacks.append(callback)

    # ---- Registration ----

    async def register(self, connection_id: str, exchange_id: str) -> None:
        """Register a connection for health monitoring."""
        async with self._lock:
            self._records[connection_id] = ConnectionHealthRecord(
                connection_id=connection_id,
                exchange_id=exchange_id,
            )
        logger.debug("Registered connection for health monitoring: %s", connection_id)

    async def unregister(self, connection_id: str) -> bool:
        """Remove a connection from health monitoring."""
        async with self._lock:
            return self._records.pop(connection_id, None) is not None

    # ---- Health Checks ----

    async def check(self, connection_id: str) -> Optional[ConnectionHealth]:
        """Perform a health check on a specific connection."""
        record = self._records.get(connection_id)
        if record is None:
            return None

        try:
            start = asyncio.get_event_loop().time()
            await asyncio.sleep(0.001)  # placeholder: actual connectivity check
            latency = (asyncio.get_event_loop().time() - start) * 1000

            record.latency_ms = latency
            record.last_checked = datetime.now(timezone.utc)
            record.consecutive_failures = 0

            if latency > self.latency_critical_ms:
                record.health = ConnectionHealth.UNHEALTHY
            elif latency > self.latency_warning_ms:
                record.health = ConnectionHealth.DEGRADED
            else:
                record.health = ConnectionHealth.HEALTHY

        except Exception as e:
            record.last_error = str(e)
            record.consecutive_failures += 1
            if record.consecutive_failures >= self.unhealthy_threshold:
                if record.health != ConnectionHealth.UNHEALTHY:
                    record.health = ConnectionHealth.UNHEALTHY
                    await self._emit_alert(connection_id, record)

        return record.health

    async def check_all(self) -> dict[str, ConnectionHealth]:
        """Perform health checks on all registered connections."""
        results: dict[str, ConnectionHealth] = {}
        for conn_id in list(self._records.keys()):
            health = await self.check(conn_id)
            if health:
                results[conn_id] = health
        return results

    async def get_health(self, connection_id: str) -> Optional[ConnectionHealthRecord]:
        """Get the health record for a connection."""
        return self._records.get(connection_id)

    async def get_unhealthy_connections(self) -> list[str]:
        """Get list of unhealthy connection IDs."""
        return [
            conn_id
            for conn_id, record in self._records.items()
            if record.health == ConnectionHealth.UNHEALTHY
        ]

    async def get_summary(self) -> dict[str, Any]:
        """Get health summary for all connections."""
        total = len(self._records)
        healthy = sum(1 for r in self._records.values() if r.health == ConnectionHealth.HEALTHY)
        degraded = sum(1 for r in self._records.values() if r.health == ConnectionHealth.DEGRADED)
        unhealthy = sum(1 for r in self._records.values() if r.health == ConnectionHealth.UNHEALTHY)

        return {
            "total": total,
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "health_ratio": healthy / max(total, 1),
        }

    async def _health_check_loop(self) -> None:
        """Periodic health check loop."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self.check_all()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Health check loop error")

    async def _emit_alert(self, connection_id: str, record: ConnectionHealthRecord) -> None:
        """Emit health alert to registered callbacks."""
        alert = {
            "type": "connection_unhealthy",
            "connection_id": connection_id,
            "exchange_id": record.exchange_id,
            "consecutive_failures": record.consecutive_failures,
            "last_error": record.last_error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception:
                logger.exception("Alert callback error")
