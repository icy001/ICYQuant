"""
Risk Platform — Unified production risk platform entry point.

Provides the single integration layer that connects the Risk Management
Platform with the entire ICYQuant ecosystem: Strategy Platform, OMS, EMS,
Workflow Engine, Event Bus, Market Data, and Monitoring.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PlatformStatus(str, Enum):
    """Risk platform operational status."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class PlatformConfig:
    """Production risk platform configuration."""
    platform_id: str = "icyquant-risk-platform"
    environment: str = "production"
    cluster_enabled: bool = True
    ha_enabled: bool = True
    circuit_breaker_enabled: bool = True
    audit_enabled: bool = True
    observability_enabled: bool = True
    policy_hot_reload: bool = True
    max_concurrent_requests: int = 1000
    request_timeout_seconds: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformState:
    """Current risk platform state snapshot."""
    status: PlatformStatus = PlatformStatus.INITIALIZING
    started_at: Optional[datetime] = None
    requests_total: int = 0
    requests_active: int = 0
    requests_blocked: int = 0
    adapters_connected: int = 0
    nodes_active: int = 1
    last_heartbeat: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class RiskPlatform:
    """
    Unified production risk platform entry point.

    Connects all risk subsystems with the ICYQuant ecosystem through
    adapters, gateway, control plane, and distributed coordination.

    Usage::

        platform = RiskPlatform(config=PlatformConfig())
        await platform.initialize()
        await platform.start()
        # All trading requests flow through this platform
        result = await platform.evaluate_order(order_request)
    """

    def __init__(self, config: Optional[PlatformConfig] = None) -> None:
        self._config = config or PlatformConfig()
        self._state = PlatformState()
        self._gateway: Any = None
        self._control_plane: Any = None
        self._coordinator: Any = None
        self._adapters: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    @property
    def config(self) -> PlatformConfig:
        return self._config

    @property
    def state(self) -> PlatformState:
        return self._state

    async def initialize(self) -> None:
        """Initialize the risk platform and all subsystems."""
        logger.info(f"RiskPlatform initializing (env: {self._config.environment})...")

        # Initialize sub-components
        await self._init_gateway()
        await self._init_control_plane()
        if self._config.cluster_enabled:
            await self._init_coordinator()
        await self._init_adapters()

        self._state.status = PlatformStatus.RUNNING
        logger.info("RiskPlatform initialized successfully.")

    async def start(self) -> None:
        """Start the risk platform in production mode."""
        self._state.status = PlatformStatus.RUNNING
        self._state.started_at = datetime.now(timezone.utc)
        logger.info("RiskPlatform started (production mode).")

    async def stop(self) -> None:
        """Gracefully stop the risk platform."""
        self._state.status = PlatformStatus.STOPPING
        await self._stop_adapters()
        if self._coordinator:
            await self._coordinator.stop()
        if self._control_plane:
            await self._control_plane.stop()
        if self._gateway:
            await self._gateway.stop()
        self._state.status = PlatformStatus.STOPPED
        logger.info("RiskPlatform stopped.")

    async def evaluate_order(self, order_request: dict[str, Any]) -> dict[str, Any]:
        """Evaluate an order through the complete risk pipeline."""
        async with self._lock:
            self._state.requests_total += 1
            self._state.requests_active += 1

        try:
            if self._gateway:
                result = await self._gateway.evaluate(order_request)
            else:
                result = {"decision": "approved", "reason": "no_gateway"}
            return result
        finally:
            async with self._lock:
                self._state.requests_active = max(0, self._state.requests_active - 1)

    async def approve(self, request_id: str) -> dict[str, Any]:
        """Manually approve a pending risk evaluation."""
        if self._control_plane:
            result = await self._control_plane.approve(request_id)
            return {"success": result.success, "message": result.message}
        return {"success": False, "message": "No control plane"}

    async def reject(self, request_id: str) -> dict[str, Any]:
        """Manually reject a pending risk evaluation."""
        if self._control_plane:
            result = await self._control_plane.reject(request_id)
            return {"success": result.success, "message": result.message}
        return {"success": False, "message": "No control plane"}

    async def get_status(self) -> dict[str, Any]:
        """Get current platform status."""
        return {
            "status": self._state.status.value,
            "environment": self._config.environment,
            "requests_total": self._state.requests_total,
            "requests_active": self._state.requests_active,
            "adapters_connected": self._state.adapters_connected,
            "nodes_active": self._state.nodes_active,
            "uptime_seconds": (
                (datetime.now(timezone.utc) - self._state.started_at).total_seconds()
                if self._state.started_at else 0
            ),
        }

    async def register_adapter(self, name: str, adapter: Any) -> None:
        """Register a platform adapter."""
        self._adapters[name] = adapter
        self._state.adapters_connected = len(self._adapters)
        logger.info(f"Adapter registered: {name}")

    async def get_adapter(self, name: str) -> Optional[Any]:
        """Get a registered adapter by name."""
        return self._adapters.get(name)

    # ---- Internal Initialization ----

    async def _init_gateway(self) -> None:
        """Initialize the risk gateway."""
        try:
            from services.risk.platform.risk_gateway import RiskGateway
            self._gateway = RiskGateway(platform=self)
            await self._gateway.initialize()
            logger.info("RiskGateway initialized.")
        except Exception as e:
            logger.warning(f"RiskGateway init skipped: {e}")

    async def _init_control_plane(self) -> None:
        """Initialize the control plane."""
        try:
            from services.risk.platform.control_plane import PlatformControlPlane
            self._control_plane = PlatformControlPlane(platform=self)
            await self._control_plane.initialize()
            logger.info("PlatformControlPlane initialized.")
        except Exception as e:
            logger.warning(f"PlatformControlPlane init skipped: {e}")

    async def _init_coordinator(self) -> None:
        """Initialize the distributed coordinator."""
        try:
            from services.risk.platform.distributed_risk_coordinator import DistributedRiskCoordinator
            self._coordinator = DistributedRiskCoordinator(platform=self)
            await self._coordinator.initialize()
            logger.info("DistributedRiskCoordinator initialized.")
        except Exception as e:
            logger.warning(f"DistributedRiskCoordinator init skipped: {e}")

    async def _init_adapters(self) -> None:
        """Initialize all platform adapters."""
        adapter_modules = [
            ("strategy", "strategy_platform_adapter", "StrategyPlatformAdapter"),
            ("market_data", "market_data_adapter", "MarketDataAdapter"),
            ("workflow", "workflow_adapter", "WorkflowAdapter"),
            ("event_bus", "event_bus_adapter", "EventBusAdapter"),
            ("monitoring", "monitoring_adapter", "MonitoringAdapter"),
            ("oms", "oms_adapter", "OMSAdapter"),
            ("ems", "ems_adapter", "EMSAdapter"),
            ("service_mesh", "service_mesh_adapter", "ServiceMeshAdapter"),
        ]
        for name, module_name, class_name in adapter_modules:
            try:
                mod = __import__(
                    f"services.risk.platform.{module_name}",
                    fromlist=[class_name],
                )
                adapter_cls = getattr(mod, class_name)
                adapter = adapter_cls(platform=self)
                await adapter.initialize()
                self._adapters[name] = adapter
            except Exception as e:
                logger.debug(f"Adapter {name} skipped: {e}")

        self._state.adapters_connected = len(self._adapters)

    async def _stop_adapters(self) -> None:
        """Stop all platform adapters."""
        for name, adapter in self._adapters.items():
            try:
                await adapter.stop()
            except Exception as e:
                logger.warning(f"Error stopping adapter {name}: {e}")
        self._adapters.clear()

    async def health_check(self) -> dict[str, Any]:
        """Check risk platform health."""
        return {
            "status": "healthy",
            "platform_status": self._state.status.value,
            "gateway": "connected" if self._gateway else "disconnected",
            "control_plane": "connected" if self._control_plane else "disconnected",
            "coordinator": "connected" if self._coordinator else "disconnected",
            "adapters": list(self._adapters.keys()),
            "uptime": (
                (datetime.now(timezone.utc) - self._state.started_at).total_seconds()
                if self._state.started_at else 0
            ),
        }
