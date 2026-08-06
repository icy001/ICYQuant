"""Service Mesh Platform Integration for the Service Mesh Platform.

Provides ``ServiceMeshPlatform`` as the main facade for the mesh
platform, orchestrating bootstrap, runtime, control plane, injection,
plugins, snapshot/restore, upgrade, compatibility, cluster, and
all integration adapters.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .bootstrap import MeshPlatformBootstrap, PlatformBootstrapPhase
from .runtime import MeshPlatformRuntime
from .container import RuntimeContainerManager
from .control_api import MeshControlAPI
from .control_service import MeshControlService
from .injector import SidecarInjector, InjectionMode
from .plugin_sdk import MeshPlugin, PluginCategory
from .plugin_manager import MeshPluginManager
from .snapshot import MeshSnapshot, SnapshotType
from .restore import MeshRestore
from .upgrade import RollingUpgradeManager, UpgradeStrategy
from .compatibility import VersionCompatibilityManager
from .cluster import MeshClusterManager
from .workflow_adapter import WorkflowAdapter
from .ai_runtime_adapter import AIRuntimeAdapter
from .discovery_adapter import ServiceDiscoveryAdapter
from .configuration_adapter import ConfigurationPlatformAdapter
from .eventbus_adapter import (
    PlatformEventBusAdapter,
    PlatformEvent,
)
from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics
from .diagnostics import PlatformDiagnostics
from .health import PlatformHealth

logger = logging.getLogger(__name__)


class ServiceMeshPlatform:
    """Unified service mesh platform entry point.

    Coordinates all mesh platform components including runtime,
    control plane, plugins, injection, snapshot/restore,
    upgrade, compatibility, cluster, and integration adapters.
    """

    def __init__(
        self,
        platform_id: str = "icyquant-mesh-platform",
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._platform_id = platform_id
        self._config = config or {}

        # Infrastructure
        self._telemetry = PlatformTelemetry()
        self._metrics = PlatformMetrics()
        self._diagnostics = PlatformDiagnostics()
        self._health = PlatformHealth()

        # Core platform components
        self._bootstrap = MeshPlatformBootstrap(
            telemetry=self._telemetry,
        )
        self._runtime = MeshPlatformRuntime(
            telemetry=self._telemetry,
            metrics=self._metrics,
        )
        self._container_manager = RuntimeContainerManager(
            telemetry=self._telemetry,
            metrics=self._metrics,
        )
        self._control_api = MeshControlAPI(
            telemetry=self._telemetry,
            metrics=self._metrics,
        )
        self._control_service = MeshControlService(
            telemetry=self._telemetry,
            metrics=self._metrics,
            diagnostics=self._diagnostics,
        )
        self._injector = SidecarInjector(
            telemetry=self._telemetry,
            metrics=self._metrics,
        )
        self._plugin_manager = MeshPluginManager(
            telemetry=self._telemetry,
            metrics=self._metrics,
        )
        self._snapshot = MeshSnapshot(
            telemetry=self._telemetry,
            metrics=self._metrics,
        )
        self._restore = MeshRestore(
            telemetry=self._telemetry,
            metrics=self._metrics,
        )
        self._upgrade_manager = RollingUpgradeManager(
            telemetry=self._telemetry,
            metrics=self._metrics,
        )
        self._compatibility = VersionCompatibilityManager(
            telemetry=self._telemetry,
            metrics=self._metrics,
        )
        self._cluster = MeshClusterManager(
            telemetry=self._telemetry,
            metrics=self._metrics,
        )

        # Integration adapters
        self._workflow_adapter = WorkflowAdapter(
            telemetry=self._telemetry,
            metrics=self._metrics,
        )
        self._ai_runtime_adapter = AIRuntimeAdapter(
            telemetry=self._telemetry,
            metrics=self._metrics,
        )
        self._discovery_adapter = ServiceDiscoveryAdapter(
            telemetry=self._telemetry,
            metrics=self._metrics,
        )
        self._configuration_adapter = ConfigurationPlatformAdapter(
            telemetry=self._telemetry,
            metrics=self._metrics,
        )
        self._eventbus_adapter = PlatformEventBusAdapter(
            telemetry=self._telemetry,
            metrics=self._metrics,
        )

        # Register bootstrap phases
        self._bootstrap.register_phase(
            PlatformBootstrapPhase.CONFIGURATION,
            self._init_configuration,
        )
        self._bootstrap.register_phase(
            PlatformBootstrapPhase.SERVICE_DISCOVERY,
            self._init_discovery,
        )
        self._bootstrap.register_phase(
            PlatformBootstrapPhase.CONTROL_PLANE,
            self._init_control_plane,
        )
        self._bootstrap.register_phase(
            PlatformBootstrapPhase.RUNTIME_CONTAINER,
            self._init_runtime_container,
        )
        self._bootstrap.register_phase(
            PlatformBootstrapPhase.PLUGIN_MANAGER,
            self._init_plugin_manager,
        )
        self._bootstrap.register_phase(
            PlatformBootstrapPhase.MESH_READY,
            self._init_mesh_ready,
        )

        # Register health checks
        self._health.register_check(
            "runtime_container",
            lambda: self._runtime.is_running,
        )
        self._health.register_check(
            "control_api",
            lambda: self._control_api.is_running,
        )
        self._health.register_check(
            "plugin_manager",
            lambda: self._plugin_manager.is_running,
        )
        self._health.register_check(
            "snapshot_service",
            lambda: True,
        )
        self._health.register_check(
            "upgrade_manager",
            lambda: True,
        )
        self._health.register_check(
            "injection_service",
            lambda: True,
        )
        self._health.register_check(
            "cluster_manager",
            lambda: True,
        )

        # Wire event subscribers
        self._eventbus_adapter.subscribe(
            self._on_platform_event,
        )

        self._started = False
        self._stopped = False

    async def startup(
        self, timeout_s: float = 60.0
    ) -> Dict[str, Any]:
        """Start the mesh platform."""
        if self._started:
            return {"success": False, "error": "Platform already started"}

        self._telemetry.log_runtime("platform_startup", "started")

        result = await self._bootstrap.startup(timeout_s=timeout_s)

        if result.get("bootstrapped"):
            self._started = True

            # Start all components
            await self._runtime.initialize(self._config)
            await self._control_api.start()
            await self._control_service.start()
            await self._plugin_manager.start()

            # Initialize adapters
            await self._workflow_adapter.initialize()
            await self._ai_runtime_adapter.initialize()
            await self._discovery_adapter.initialize()
            await self._configuration_adapter.initialize(
                self._config
            )
            await self._eventbus_adapter.initialize()

            self._metrics.increment_runtime_total()

            await self._eventbus_adapter.publish_mesh_started(
                {"platform_id": self._platform_id}
            )

            self._telemetry.log_runtime(
                "platform_startup", "completed",
                {"platform_id": self._platform_id},
            )
            logger.info(
                "Service mesh platform '%s' started successfully.",
                self._platform_id,
            )
        else:
            self._telemetry.log_error(
                "platform",
                "startup_failed",
                f"Failed at phase: {result.get('failed_phase')}",
            )

        return result

    async def shutdown(
        self, timeout_s: float = 30.0
    ) -> Dict[str, Any]:
        """Shutdown the mesh platform."""
        if not self._started:
            return {"success": False, "error": "Platform not started"}

        # Shutdown components in reverse order
        await self._workflow_adapter.shutdown()
        await self._ai_runtime_adapter.shutdown()
        await self._discovery_adapter.shutdown()
        await self._configuration_adapter.shutdown()
        await self._eventbus_adapter.shutdown()

        await self._plugin_manager.stop()
        await self._control_api.stop()
        await self._control_service.stop()

        # Stop all containers
        await self._container_manager.stop_all()

        await self._runtime.stop()

        self._started = False
        self._stopped = True

        self._telemetry.log_runtime(
            "platform_shutdown", "completed",
        )
        logger.info("Service mesh platform shut down.")
        return {"success": True}

    async def reload(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Hot-reload the mesh platform."""
        self._metrics.increment_counter(
            "icyquant_mesh_platform_reload_total"
        )

        if config:
            await self._configuration_adapter.update_config(config)

        result = await self._runtime.reload(config)

        self._telemetry.log_runtime(
            "platform_reload", "completed",
        )
        return result

    async def health_check(self) -> Dict[str, Any]:
        return await self._health.check()

    async def create_snapshot(
        self,
        snapshot_type: SnapshotType = SnapshotType.FULL,
    ) -> Dict[str, Any]:
        return self._snapshot.create_snapshot(snapshot_type)

    async def restore_from_snapshot(
        self,
        snapshot_data: Dict[str, Any],
        full_restore: bool = True,
    ) -> Dict[str, Any]:
        return await self._restore.restore(
            snapshot_data, full_restore
        )

    async def start_upgrade(
        self,
        target_version: str,
        strategy: UpgradeStrategy = UpgradeStrategy.CANARY,
    ) -> Dict[str, Any]:
        return await self._upgrade_manager.start_upgrade(
            target_version, strategy
        )

    async def inject_sidecar(
        self,
        service_name: str,
        mode: InjectionMode = InjectionMode.MANUAL,
    ) -> Dict[str, Any]:
        return await self._injector.inject(service_name, mode)

    async def register_plugin(
        self,
        plugin_class: type,
        category: PluginCategory = PluginCategory.CUSTOM,
    ) -> Dict[str, Any]:
        result = await self._plugin_manager.install(
            plugin_class, category
        )
        if result.get("success"):
            plugin_id = result["plugin_id"]
            await self._plugin_manager.load(plugin_id)
        return result

    async def join_cluster(
        self,
        host: str = "localhost",
        port: int = 8080,
    ) -> Dict[str, Any]:
        return await self._cluster.join_cluster(
            host=host, port=port
        )

    # Bootstrap phase initializers
    def _init_configuration(self) -> Dict[str, Any]:
        self._telemetry.log_runtime(
            "config_init", "started",
        )
        return {"success": True}

    def _init_discovery(self) -> Dict[str, Any]:
        return {"success": True}

    def _init_control_plane(self) -> Dict[str, Any]:
        return {"success": True}

    def _init_runtime_container(self) -> Dict[str, Any]:
        return {"success": True}

    def _init_plugin_manager(self) -> Dict[str, Any]:
        return {"success": True}

    def _init_mesh_ready(self) -> Dict[str, Any]:
        self._telemetry.log_platform_event(
            "mesh_platform_ready", "platform",
        )
        return {"success": True, "platform_id": self._platform_id}

    # Event handler
    async def _on_platform_event(
        self, event: Dict[str, Any]
    ) -> None:
        self._telemetry.log_platform_event(
            event.get("event_type", "unknown"),
            "event_bus",
            event,
        )

    # Component accessors
    @property
    def platform_id(self) -> str:
        return self._platform_id

    @property
    def is_running(self) -> bool:
        return self._started

    @property
    def runtime(self) -> MeshPlatformRuntime:
        return self._runtime

    @property
    def container_manager(self) -> RuntimeContainerManager:
        return self._container_manager

    @property
    def control_api(self) -> MeshControlAPI:
        return self._control_api

    @property
    def control_service(self) -> MeshControlService:
        return self._control_service

    @property
    def injector(self) -> SidecarInjector:
        return self._injector

    @property
    def plugin_manager(self) -> MeshPluginManager:
        return self._plugin_manager

    @property
    def snapshot_service(self) -> MeshSnapshot:
        return self._snapshot

    @property
    def restore_service(self) -> MeshRestore:
        return self._restore

    @property
    def upgrade_manager(self) -> RollingUpgradeManager:
        return self._upgrade_manager

    @property
    def compatibility(self) -> VersionCompatibilityManager:
        return self._compatibility

    @property
    def cluster(self) -> MeshClusterManager:
        return self._cluster

    @property
    def workflow_adapter(self) -> WorkflowAdapter:
        return self._workflow_adapter

    @property
    def ai_runtime_adapter(self) -> AIRuntimeAdapter:
        return self._ai_runtime_adapter

    @property
    def discovery_adapter(self) -> ServiceDiscoveryAdapter:
        return self._discovery_adapter

    @property
    def configuration_adapter(self) -> ConfigurationPlatformAdapter:
        return self._configuration_adapter

    @property
    def eventbus_adapter(self) -> PlatformEventBusAdapter:
        return self._eventbus_adapter

    @property
    def telemetry(self) -> PlatformTelemetry:
        return self._telemetry

    @property
    def metrics(self) -> PlatformMetrics:
        return self._metrics

    @property
    def diagnostics(self) -> PlatformDiagnostics:
        return self._diagnostics

    @property
    def health_service(self) -> PlatformHealth:
        return self._health

    def get_stats(self) -> Dict[str, Any]:
        return {
            "platform_id": self._platform_id,
            "running": self._started,
            "bootstrap": self._bootstrap.get_stats(),
            "runtime": self._runtime.get_stats(),
            "containers": self._container_manager.get_stats(),
            "control_api": self._control_api.get_stats(),
            "control_service": self._control_service.get_stats(),
            "injection": self._injector.get_stats(),
            "plugins": self._plugin_manager.get_stats(),
            "snapshot": self._snapshot.get_stats(),
            "restore": self._restore.get_stats(),
            "upgrade": self._upgrade_manager.get_stats(),
            "compatibility": self._compatibility.get_stats(),
            "cluster": self._cluster.get_stats(),
            "workflow": self._workflow_adapter.get_stats(),
            "ai_runtime": self._ai_runtime_adapter.get_stats(),
            "discovery": self._discovery_adapter.get_stats(),
            "configuration": self._configuration_adapter.get_stats(),
            "eventbus": self._eventbus_adapter.get_stats(),
            "metrics": self._metrics.get_summary(),
            "diagnostics": self._diagnostics.get_stats(),
            "health": self._health.get_stats(),
        }

    def __repr__(self) -> str:
        return (
            f"ServiceMeshPlatform("
            f"id={self._platform_id}, "
            f"running={self._started})"
        )
