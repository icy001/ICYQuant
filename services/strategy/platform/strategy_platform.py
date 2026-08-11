"""
Production Strategy Platform — Unified Entry Point.

The StrategyPlatform is the top-level orchestrator that coordinates
all platform subsystems: control plane, deployment, lifecycle,
adapters, event bridge, and APIs.
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
    """Platform operational status."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class PlatformConfig:
    """Platform-level configuration."""
    platform_id: str = "icyquant-strategy-platform"
    max_concurrent_strategies: int = 100
    heartbeat_interval_seconds: float = 5.0
    shutdown_timeout_seconds: float = 30.0
    enable_auto_recovery: bool = True
    enable_event_bridge: bool = True
    enable_audit: bool = True
    enable_telemetry: bool = True
    adapter_timeout_seconds: float = 10.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformContext:
    """Runtime context shared across platform subsystems."""
    platform_id: str
    started_at: datetime
    config: PlatformConfig
    strategies_active: int = 0
    events_processed: int = 0
    errors_total: int = 0
    last_heartbeat: Optional[datetime] = None


class StrategyPlatform:
    """
    Unified Production Strategy Platform.

    Top-level orchestrator managing the complete lifecycle of all
    production strategies, coordinating the control plane, deployment
    pipeline, adapters, event bus, and external APIs.

    Usage::

        platform = StrategyPlatform(config)
        await platform.initialize()
        await platform.start()
        # ... strategies are registered, deployed, and running ...
        await platform.stop()
    """

    def __init__(self, config: Optional[PlatformConfig] = None) -> None:
        self._config = config or PlatformConfig()
        self._status = PlatformStatus.STOPPED
        self._context: Optional[PlatformContext] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        # Subsystems — injected after initialization
        self._control_plane: Any = None
        self._gateway: Any = None
        self._lifecycle_controller: Any = None
        self._deployment_manager: Any = None
        self._catalog: Any = None
        self._event_bridge: Any = None
        self._event_stream: Any = None
        self._audit_center: Any = None
        self._observability: Any = None

        # Adapters
        self._adapters: dict[str, Any] = {}

    # ---- Properties ----

    @property
    def status(self) -> PlatformStatus:
        return self._status

    @property
    def context(self) -> Optional[PlatformContext]:
        return self._context

    @property
    def config(self) -> PlatformConfig:
        return self._config

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the platform and all subsystems."""
        if self._status != PlatformStatus.STOPPED:
            logger.warning(f"Platform already in state: {self._status}")
            return

        self._status = PlatformStatus.INITIALIZING
        logger.info("Initializing Production Strategy Platform...")

        self._context = PlatformContext(
            platform_id=self._config.platform_id,
            started_at=datetime.now(timezone.utc),
            config=self._config,
        )

        # Initialize subsystems in dependency order
        if self._config.enable_audit:
            from services.strategy.platform.audit_center import AuditCenter
            self._audit_center = AuditCenter()
            await self._audit_center.initialize()

        if self._config.enable_event_bridge:
            from services.strategy.platform.event_bridge import EventBridge
            self._event_bridge = EventBridge()
            await self._event_bridge.initialize()

        from services.strategy.platform.event_stream import EventStream
        self._event_stream = EventStream(event_bridge=self._event_bridge)
        await self._event_stream.initialize()

        from services.strategy.platform.control_plane import ControlPlane
        self._control_plane = ControlPlane(
            audit_center=self._audit_center,
            event_bridge=self._event_bridge,
        )
        await self._control_plane.initialize()

        from services.strategy.platform.strategy_gateway import StrategyGateway
        self._gateway = StrategyGateway(control_plane=self._control_plane)
        await self._gateway.initialize()

        from services.strategy.platform.lifecycle_controller import LifecycleController
        self._lifecycle_controller = LifecycleController(
            event_bridge=self._event_bridge,
            audit_center=self._audit_center,
        )
        await self._lifecycle_controller.initialize()

        from services.strategy.platform.deployment_manager import DeploymentManager
        self._deployment_manager = DeploymentManager(
            lifecycle_controller=self._lifecycle_controller,
            audit_center=self._audit_center,
        )
        await self._deployment_manager.initialize()

        from services.strategy.platform.strategy_catalog import StrategyCatalog
        self._catalog = StrategyCatalog()
        await self._catalog.initialize()

        if self._config.enable_telemetry:
            from services.strategy.platform.observability import StrategyObservability
            self._observability = StrategyObservability()
            await self._observability.initialize()

        # Initialize adapters
        await self._initialize_adapters()

        logger.info("Production Strategy Platform initialized successfully.")

    async def start(self) -> None:
        """Start the platform and all subsystems."""
        if self._status not in (PlatformStatus.INITIALIZING, PlatformStatus.STOPPED):
            raise RuntimeError(f"Cannot start from state: {self._status}")

        self._status = PlatformStatus.RUNNING
        logger.info("Starting Production Strategy Platform...")

        # Start event stream
        if self._event_stream:
            await self._event_stream.start()

        # Start control plane
        if self._control_plane:
            await self._control_plane.start()

        # Start heartbeat
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        await self._record_audit("platform.start", "Platform started")

        logger.info("Production Strategy Platform is RUNNING.")

    async def stop(self) -> None:
        """Gracefully stop the platform."""
        if self._status in (PlatformStatus.STOPPING, PlatformStatus.STOPPED):
            return

        self._status = PlatformStatus.STOPPING
        logger.info("Stopping Production Strategy Platform...")

        await self._record_audit("platform.stop", "Platform stopping")

        # Cancel heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Stop subsystems in reverse order
        for subsystem in [
            self._observability,
            self._deployment_manager,
            self._lifecycle_controller,
            self._gateway,
            self._control_plane,
            self._event_stream,
            self._event_bridge,
            self._audit_center,
        ]:
            if subsystem and hasattr(subsystem, 'stop'):
                try:
                    await subsystem.stop()
                except Exception as e:
                    logger.error(f"Error stopping subsystem: {e}")

        # Stop adapters
        for name, adapter in self._adapters.items():
            if hasattr(adapter, 'stop'):
                try:
                    await adapter.stop()
                except Exception as e:
                    logger.error(f"Error stopping adapter {name}: {e}")

        self._status = PlatformStatus.STOPPED
        logger.info("Production Strategy Platform stopped.")

    # ---- Subsystem Access ----

    @property
    def control_plane(self) -> Any:
        return self._control_plane

    @property
    def gateway(self) -> Any:
        return self._gateway

    @property
    def lifecycle_controller(self) -> Any:
        return self._lifecycle_controller

    @property
    def deployment_manager(self) -> Any:
        return self._deployment_manager

    @property
    def catalog(self) -> Any:
        return self._catalog

    @property
    def event_bridge(self) -> Any:
        return self._event_bridge

    @property
    def event_stream(self) -> Any:
        return self._event_stream

    @property
    def audit_center(self) -> Any:
        return self._audit_center

    @property
    def observability(self) -> Any:
        return self._observability

    def get_adapter(self, name: str) -> Optional[Any]:
        """Get a registered adapter by name."""
        return self._adapters.get(name)

    # ---- Adapter Registration ----

    async def register_adapter(self, name: str, adapter: Any) -> None:
        """Register a platform adapter."""
        self._adapters[name] = adapter
        if hasattr(adapter, 'initialize'):
            await adapter.initialize()
        logger.info(f"Adapter registered: {name}")

    # ---- Health ----

    async def health_check(self) -> dict[str, Any]:
        """Return platform health status."""
        checks = {
            "status": self._status.value,
            "control_plane": "ok" if self._control_plane else "not_initialized",
            "gateway": "ok" if self._gateway else "not_initialized",
            "lifecycle": "ok" if self._lifecycle_controller else "not_initialized",
            "deployment": "ok" if self._deployment_manager else "not_initialized",
            "catalog": "ok" if self._catalog else "not_initialized",
            "event_bridge": "ok" if self._event_bridge else "not_initialized",
            "event_stream": "ok" if self._event_stream else "not_initialized",
            "audit": "ok" if self._audit_center else "not_initialized",
            "observability": "ok" if self._observability else "not_initialized",
            "adapters": list(self._adapters.keys()),
        }
        if self._context:
            checks["context"] = {
                "strategies_active": self._context.strategies_active,
                "events_processed": self._context.events_processed,
                "errors_total": self._context.errors_total,
                "uptime_seconds": (
                    datetime.now(timezone.utc) - self._context.started_at
                ).total_seconds(),
            }
        return checks

    # ---- Internal ----

    async def _initialize_adapters(self) -> None:
        """Initialize all platform adapters lazily."""
        adapter_classes = [
            ("feature_store", "services.strategy.platform.feature_store_adapter", "FeatureStoreAdapter"),
            ("market_data", "services.strategy.platform.market_data_adapter", "MarketDataAdapter"),
            ("workflow", "services.strategy.platform.workflow_adapter", "WorkflowAdapter"),
            ("scheduler", "services.strategy.platform.scheduler_adapter", "SchedulerAdapter"),
            ("research", "services.strategy.platform.research_adapter", "ResearchAdapter"),
            ("risk_engine", "services.strategy.platform.risk_engine_adapter", "RiskEngineAdapter"),
            ("oms", "services.strategy.platform.oms_adapter", "OMSAdapter"),
            ("ems", "services.strategy.platform.ems_adapter", "EMSAdapter"),
            ("monitoring", "services.strategy.platform.monitoring_adapter", "MonitoringAdapter"),
        ]
        for name, module_path, class_name in adapter_classes:
            try:
                import importlib
                module = importlib.import_module(module_path)
                adapter_cls = getattr(module, class_name)
                adapter = adapter_cls()
                if hasattr(adapter, 'initialize'):
                    await adapter.initialize()
                self._adapters[name] = adapter
                logger.debug(f"Adapter initialized: {name}")
            except Exception as e:
                logger.warning(f"Failed to initialize adapter {name}: {e}")

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat for platform health monitoring."""
        while True:
            try:
                await asyncio.sleep(self._config.heartbeat_interval_seconds)
                if self._context:
                    self._context.last_heartbeat = datetime.now(timezone.utc)
                if self._event_bridge:
                    await self._event_bridge.emit(
                        "platform.heartbeat",
                        {"platform_id": self._config.platform_id},
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                if self._context:
                    self._context.errors_total += 1

    async def _record_audit(self, category: str, message: str, **kwargs: Any) -> None:
        """Record an audit event if audit center is enabled."""
        if self._audit_center and self._config.enable_audit:
            try:
                await self._audit_center.record(
                    category=category,
                    message=message,
                    platform_id=self._config.platform_id,
                    **kwargs,
                )
            except Exception as e:
                logger.error(f"Audit recording failed: {e}")
