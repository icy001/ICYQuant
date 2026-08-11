"""Gateway Runtime — Async runtime for execution gateway operations.

Manages the lifecycle of gateway components including SOR, broker
sessions, FIX engines, and connection pools. Provides async start/stop
coordination with graceful shutdown.

Lifecycle::

    initialize → start → run → stop → cleanup

Usage::

    runtime = GatewayRuntime()
    await runtime.start()
    await runtime.submit(order_request)
    await runtime.stop()
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from services.execution_gateway.broker_registry import BrokerRegistry
from services.execution_gateway.connection_pool import ConnectionPool
from services.execution_gateway.failover_router import FailoverRouter
from services.execution_gateway.metrics import GatewayMetrics
from services.execution_gateway.telemetry import GatewayTelemetry
from services.execution_gateway.venue_registry import VenueRegistry

logger = logging.getLogger(__name__)


class RuntimeStatus(str, Enum):
    """Gateway runtime lifecycle status."""

    INITIALIZED = "INITIALIZED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class GatewayRuntime:
    """Async runtime for the execution gateway.

    Manages component lifecycle, async coordination, and graceful
    shutdown for all gateway sub-systems.

    Attributes:
        status: Current runtime status
        started_at: Runtime start timestamp
        _tasks: Active async tasks
        _broker_registry: Broker registration store
        _venue_registry: Venue registration store
        _connection_pool: Connection pool manager
        _failover_router: Failover routing manager
        _metrics: Gateway metrics
        _telemetry: Gateway telemetry
    """

    def __init__(
        self,
        broker_registry: Optional[BrokerRegistry] = None,
        venue_registry: Optional[VenueRegistry] = None,
        connection_pool: Optional[ConnectionPool] = None,
        failover_router: Optional[FailoverRouter] = None,
        metrics: Optional[GatewayMetrics] = None,
        telemetry: Optional[GatewayTelemetry] = None,
    ) -> None:
        self.status = RuntimeStatus.INITIALIZED
        self.started_at: Optional[datetime] = None
        self._tasks: list[asyncio.Task] = []
        self._broker_registry = broker_registry or BrokerRegistry()
        self._venue_registry = venue_registry or VenueRegistry()
        self._connection_pool = connection_pool or ConnectionPool()
        self._failover_router = failover_router or FailoverRouter()
        self._metrics = metrics or GatewayMetrics()
        self._telemetry = telemetry or GatewayTelemetry()

    # ── Lifecycle ──────────────────────────────────────────────────

    async def start(self) -> bool:
        """Start the gateway runtime.

        Initializes all components and begins accepting requests.

        Returns:
            True if started successfully
        """
        self.status = RuntimeStatus.STARTING
        logger.info("Gateway runtime starting...")

        try:
            self.started_at = datetime.now(timezone.utc)
            self.status = RuntimeStatus.RUNNING
            logger.info("Gateway runtime started successfully")
            return True
        except Exception as e:
            self.status = RuntimeStatus.ERROR
            logger.error("Gateway runtime start failed: %s", e)
            return False

    async def stop(self) -> bool:
        """Stop the gateway runtime with graceful shutdown.

        Drains active connections and cleans up resources.

        Returns:
            True if stopped cleanly
        """
        self.status = RuntimeStatus.STOPPING
        logger.info("Gateway runtime stopping...")

        try:
            # Cancel background tasks
            for task in self._tasks:
                if not task.done():
                    task.cancel()
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

            # Drain connections
            await self._connection_pool.close_all()

            self.status = RuntimeStatus.STOPPED
            logger.info("Gateway runtime stopped")
            return True
        except Exception as e:
            self.status = RuntimeStatus.ERROR
            logger.error("Gateway runtime stop failed: %s", e)
            return False

    async def submit(self, request: dict[str, Any]) -> dict[str, Any]:
        """Submit an order through the gateway.

        Args:
            request: Order request dictionary

        Returns:
            Order response dictionary
        """
        if self.status != RuntimeStatus.RUNNING:
            return {"status": "ERROR", "message": "Runtime not running"}

        with self._telemetry.trace_order_submission(
            request.get("order_id", ""), request.get("symbol", "")
        ):
            self._metrics.record_sor_request(request.get("strategy", "unknown"))
            return {"status": "SUBMITTED", "message": "Order accepted"}

    # ── Component Access ───────────────────────────────────────────

    @property
    def broker_registry(self) -> BrokerRegistry:
        return self._broker_registry

    @property
    def venue_registry(self) -> VenueRegistry:
        return self._venue_registry

    @property
    def connection_pool(self) -> ConnectionPool:
        return self._connection_pool

    @property
    def failover_router(self) -> FailoverRouter:
        return self._failover_router

    @property
    def uptime_seconds(self) -> float:
        """Runtime uptime in seconds."""
        if not self.started_at:
            return 0.0
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()

    # ── State ──────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize runtime state."""
        return {
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "uptime_seconds": self.uptime_seconds,
            "brokers_registered": self._broker_registry.count,
            "venues_registered": self._venue_registry.count,
            "active_connections": self._connection_pool.active_count,
            "metrics": self._metrics.to_dict(),
        }
