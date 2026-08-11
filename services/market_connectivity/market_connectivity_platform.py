"""
Unified Market Connectivity Platform.

Central entry point for all exchange connectivity, managing the full
lifecycle of connections, sessions, and protocols across multiple
exchanges and market data sources.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .connectivity_controller import ConnectivityController
from .connectivity_manager import ConnectivityManager
from .connectivity_registry import ConnectivityRegistry
from .connectivity_runtime import ConnectivityRuntime, ConnectivityRuntimeConfig, ConnectivityRuntimeStatus
from .diagnostics import ConnectivityDiagnostics
from .health import ConnectivityHealthChecker, ProbeType

logger = logging.getLogger(__name__)


class PlatformState(str, Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    DEGRADED = "degraded"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class PlatformConfig:
    platform_id: str = "icyquant-market-connectivity"
    auto_discover: bool = True
    auto_reconnect: bool = True
    health_check_interval: float = 5.0
    metrics_enabled: bool = True
    telemetry_enabled: bool = True
    max_concurrent_connections: int = 256
    graceful_shutdown_timeout: float = 30.0


class MarketConnectivityPlatform:
    """
    Unified Market Connectivity Platform.

    Central entry point that coordinates all exchange connections,
    session management, protocol negotiation, and health monitoring.

    Usage::

        platform = MarketConnectivityPlatform()
        await platform.initialize(config)
        await platform.start()

        await platform.connect("binance")
        await platform.connect("okx")

        status = await platform.status()
        await platform.disconnect_all()
        await platform.shutdown()
    """

    def __init__(self, config: Optional[PlatformConfig] = None) -> None:
        self.config = config or PlatformConfig()
        self._state = PlatformState.CREATED
        self._registry = ConnectivityRegistry()
        self._manager = ConnectivityManager(self._registry)
        self._controller = ConnectivityController(self._registry, self._manager)
        self._runtime = ConnectivityRuntime(
            ConnectivityRuntimeConfig(
                platform_id=self.config.platform_id,
                auto_reconnect=self.config.auto_reconnect,
                health_check_interval=self.config.health_check_interval,
                max_concurrent_connections=self.config.max_concurrent_connections,
            )
        )
        self._health_checker = ConnectivityHealthChecker()
        self._diagnostics = ConnectivityDiagnostics()
        self._started_at: Optional[datetime] = None

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the platform and all subsystems."""
        if self._state != PlatformState.CREATED:
            logger.warning("Platform already initialized, state=%s", self._state.value)
            return

        self._state = PlatformState.INITIALIZING
        logger.info("Initializing Market Connectivity Platform...")

        await self._registry.initialize()
        await self._manager.initialize()
        await self._controller.initialize()
        await self._runtime.initialize()
        await self._health_checker.initialize()
        await self._diagnostics.initialize()

        self._state = PlatformState.DISCONNECTED
        logger.info("Market Connectivity Platform initialized.")

    async def start(self) -> None:
        """Start the platform runtime."""
        if self._state != PlatformState.DISCONNECTED:
            logger.warning("Cannot start: platform in state=%s", self._state.value)
            return

        logger.info("Starting Market Connectivity Platform...")
        await self._runtime.start()
        self._started_at = datetime.now(timezone.utc)
        self._state = PlatformState.RUNNING
        logger.info("Market Connectivity Platform started.")

    async def shutdown(self) -> None:
        """Gracefully shut down all connections and the platform."""
        if self._state in (PlatformState.DISCONNECTED, PlatformState.CREATED):
            return

        logger.info("Shutting down Market Connectivity Platform...")
        self._state = PlatformState.DISCONNECTING

        try:
            await asyncio.wait_for(
                self.disconnect_all(),
                timeout=self.config.graceful_shutdown_timeout,
            )
        except asyncio.TimeoutError:
            logger.error("Shutdown timed out, forcing disconnect.")

        await self._runtime.stop()
        await self._diagnostics.stop()
        await self._health_checker.stop()

        self._state = PlatformState.DISCONNECTED
        logger.info("Market Connectivity Platform shut down.")

    # ---- Connectivity Operations ----

    async def connect(self, exchange_id: str, **kwargs: Any) -> bool:
        """Connect to a specific exchange."""
        if self._state != PlatformState.RUNNING:
            logger.error("Cannot connect: platform not running (state=%s)", self._state.value)
            return False

        return await self._controller.connect_exchange(exchange_id, **kwargs)

    async def disconnect(self, exchange_id: str) -> bool:
        """Disconnect from a specific exchange."""
        return await self._controller.disconnect_exchange(exchange_id)

    async def reconnect(self, exchange_id: str) -> bool:
        """Reconnect to a specific exchange."""
        return await self._controller.reconnect_exchange(exchange_id)

    async def disconnect_all(self) -> None:
        """Disconnect all active exchange connections."""
        active_exchanges = await self._controller.get_active_exchanges()
        tasks = [self.disconnect(eid) for eid in active_exchanges]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def discover(self) -> list[str]:
        """Discover available exchanges and endpoints."""
        return await self._controller.discover_exchanges()

    # ---- Status & Health ----

    async def status(self) -> dict[str, Any]:
        """Get comprehensive platform status."""
        runtime_status = await self._runtime.get_status()
        health_report = await self._health_checker.check_all(ProbeType.READINESS)
        registry_summary = await self._registry.get_summary()

        return {
            "platform_id": self.config.platform_id,
            "state": self._state.value,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "uptime_seconds": (
                (datetime.now(timezone.utc) - self._started_at).total_seconds()
                if self._started_at
                else 0.0
            ),
            "runtime": runtime_status,
            "health": {
                "overall": health_report.overall_status.value,
                "components": [
                    {"name": c.component, "status": c.status.value}
                    for c in health_report.components
                ],
            },
            "registry": registry_summary,
        }

    async def get_active_exchanges(self) -> list[str]:
        """Get list of currently connected exchanges."""
        return await self._controller.get_active_exchanges()

    async def get_exchange_info(self, exchange_id: str) -> Optional[dict[str, Any]]:
        """Get detailed information about a specific exchange."""
        return await self._controller.get_exchange_info(exchange_id)

    # ---- Diagnostics ----

    async def run_diagnostics(self) -> dict[str, Any]:
        """Run full platform diagnostics."""
        report = await self._diagnostics.run_full_diagnostics()
        return {
            "overall_status": report.overall_status.value,
            "checks": [
                {
                    "name": c.name,
                    "category": c.category,
                    "status": c.status.value,
                    "message": c.message,
                    "duration_ms": c.duration_ms,
                }
                for c in report.checks
            ],
            "summary": report.summary,
            "recommendations": report.recommendations,
        }

    # ---- Properties ----

    @property
    def state(self) -> PlatformState:
        return self._state

    @property
    def registry(self) -> ConnectivityRegistry:
        return self._registry

    @property
    def controller(self) -> ConnectivityController:
        return self._controller

    @property
    def runtime(self) -> ConnectivityRuntime:
        return self._runtime
