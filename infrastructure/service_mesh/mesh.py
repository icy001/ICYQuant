"""Service Mesh unified entry point for ICYQuant.

Provides ``ServiceMesh`` as the main facade for the service mesh,
coordinating bootstrap, runtime, lifecycle, and synchronization
across all mesh components.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .bootstrap import BootstrapPhase, MeshBootstrap
from .configuration import MeshConfiguration
from .context import MeshContext
from .control_plane import ControlPlane
from .data_plane import DataPlane
from .discovery import MeshDiscovery
from .events import MeshEvent, MeshEventPublisher
from .exceptions import MeshBootstrapError, MeshRuntimeError
from .health import MeshHealth
from .lifecycle import MeshLifecycle, MeshState
from .manager import MeshManager
from .metrics import MeshMetrics
from .models import (
    MeshMetadata,
    MeshService,
    ProxyConfig,
    ProxyType,
)
from .proxy import MeshProxy
from .registry import MeshRegistry
from .runtime import MeshRuntime
from .sidecar import Sidecar
from .synchronization import MeshSynchronizer
from .telemetry import MeshTelemetry

logger = logging.getLogger(__name__)


class ServiceMesh:
    """Unified service mesh entry point.

    Coordinates bootstrap, runtime management, lifecycle
    transitions, and synchronization for all mesh components.
    """

    def __init__(
        self,
        mesh_id: str = "icyquant-mesh",
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._context = MeshContext()
        self._metadata = MeshMetadata(mesh_id=mesh_id)
        self._config = config or {}

        # Core components
        self._publisher = MeshEventPublisher()
        self._metrics = MeshMetrics()
        self._telemetry = MeshTelemetry()
        self._health = MeshHealth()
        self._lifecycle = MeshLifecycle()
        self._bootstrap = MeshBootstrap(
            self._context, self._lifecycle
        )
        self._runtime = MeshRuntime(self._context)
        self._control_plane = ControlPlane(self._context)
        self._data_plane = DataPlane(self._context)
        self._proxy = MeshProxy(context=self._context)
        self._registry = MeshRegistry(self._context)
        self._discovery = MeshDiscovery(self._context)
        self._configuration = MeshConfiguration(self._context)
        self._synchronizer = MeshSynchronizer(self._context)
        self._manager = MeshManager(self._context)

        # Wire publishers
        for comp in [
            self._runtime,
            self._control_plane,
            self._data_plane,
            self._proxy,
            self._synchronizer,
            self._bootstrap,
            self._discovery,
        ]:
            if hasattr(comp, "set_publisher"):
                comp.set_publisher(self._publisher)

        # Register bootstrap phases
        self._bootstrap.register_phase(
            BootstrapPhase.CONFIGURATION,
            self._init_configuration,
        )
        self._bootstrap.register_phase(
            BootstrapPhase.SERVICE_DISCOVERY,
            self._init_discovery,
        )
        self._bootstrap.register_phase(
            BootstrapPhase.CONTROL_PLANE,
            self._init_control_plane,
        )
        self._bootstrap.register_phase(
            BootstrapPhase.DATA_PLANE,
            self._init_data_plane,
        )
        self._bootstrap.register_phase(
            BootstrapPhase.SIDECAR_RUNTIME,
            self._init_sidecar_runtime,
        )
        self._bootstrap.register_phase(
            BootstrapPhase.MESH_READY,
            self._init_mesh_ready,
        )

        # Register health checks
        self._health.register_check(
            "control_plane",
            lambda: self._control_plane.is_running,
        )
        self._health.register_check(
            "data_plane",
            lambda: self._data_plane.is_running,
        )
        self._health.register_check(
            "sidecar",
            lambda: len(self._manager.list_sidecars()) >= 0,
        )
        self._health.register_check(
            "proxy",
            lambda: self._proxy.is_running,
        )
        self._health.register_check(
            "configuration",
            lambda: self._configuration.get_stats()["version"] >= 0,
        )

        # Register telemetry listener
        self._publisher.subscribe(
            self._on_mesh_event,
        )

        self._started = False
        self._stopped = False

    async def startup(
        self, timeout_s: float = 60.0
    ) -> Dict[str, Any]:
        """Start the service mesh."""
        if self._started:
            return {"success": False, "error": "Mesh already started"}

        self._metrics.increment_runtime_total()
        self._telemetry.log_mesh_event("mesh_start", "service_mesh")

        result = await self._bootstrap.startup(timeout_s=timeout_s)

        if result.get("bootstrapped"):
            self._started = True
            self._lifecycle.transition_to(
                MeshState.RUNNING, "mesh_started"
            )
            await self._runtime.start(self._config)
            await self._control_plane.start()
            await self._data_plane.start()
            await self._proxy.start()

            # Set up default routing rules
            from .models import RoutingRule
            default_rules = [
                RoutingRule("default-api", "backend", path="/api"),
                RoutingRule("default-all", "backend", path="/"),
            ]
            self._data_plane.update_routing_rules(default_rules)

            self._telemetry.log_mesh_event(
                "mesh_ready", "service_mesh"
            )
            logger.info(
                "Service mesh '%s' started successfully.",
                self._metadata.mesh_id,
            )
        else:
            self._telemetry.log_error(
                "service_mesh",
                "bootstrap_failed",
                f"Failed at phase: {result.get('failed_phase')}",
            )

        return result

    async def shutdown(
        self, timeout_s: float = 30.0
    ) -> Dict[str, Any]:
        """Shutdown the service mesh."""
        if not self._started:
            return {"success": False, "error": "Mesh not started"}

        self._lifecycle.transition_to(
            MeshState.DRAINING, "mesh_shutdown_started"
        )

        # Stop sidecars
        sidecars = self._manager.list_sidecars()
        for sc_info in sidecars:
            try:
                sc = self._manager.get_sidecar(
                    sc_info["sidecar_id"]
                )
                if sc:
                    await sc.stop()
            except Exception:
                pass

        # Stop data plane
        await self._data_plane.stop()
        await self._proxy.stop()

        # Stop runtime
        await self._runtime.stop()

        self._started = False
        self._stopped = True
        self._lifecycle.transition_to(
            MeshState.STOPPED, "mesh_shutdown_complete"
        )

        self._telemetry.log_mesh_event(
            "mesh_stop", "service_mesh"
        )
        logger.info("Service mesh shutdown complete.")
        return {"success": True}

    async def reload(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Hot-reload the service mesh configuration."""
        self._lifecycle.transition_to(
            MeshState.RELOADING, "mesh_reload_started"
        )
        self._metrics.increment_reload_total()

        result = await self._runtime.reload(config)

        self._lifecycle.transition_to(
            MeshState.RUNNING, "mesh_reload_complete"
        )

        if config:
            try:
                self._configuration.apply_configuration(config)
                await self._control_plane.publish_configuration(
                    "routing"
                )
            except Exception as exc:
                self._telemetry.log_error(
                    "control_plane",
                    "config_apply_failed",
                    str(exc),
                )

        return result

    async def health_check(self) -> Dict[str, Any]:
        """Run a health check of the mesh."""
        return await self._health.check()

    # Component accessors
    @property
    def context(self) -> MeshContext:
        return self._context

    @property
    def metadata(self) -> MeshMetadata:
        return self._metadata

    @property
    def lifecycle(self) -> MeshLifecycle:
        return self._lifecycle

    @property
    def is_running(self) -> bool:
        return self._started

    @property
    def control_plane(self) -> ControlPlane:
        return self._control_plane

    @property
    def data_plane(self) -> DataPlane:
        return self._data_plane

    @property
    def proxy(self) -> MeshProxy:
        return self._proxy

    @property
    def runtime(self) -> MeshRuntime:
        return self._runtime

    @property
    def manager(self) -> MeshManager:
        return self._manager

    @property
    def registry(self) -> MeshRegistry:
        return self._registry

    @property
    def discovery(self) -> MeshDiscovery:
        return self._discovery

    @property
    def configuration(self) -> MeshConfiguration:
        return self._configuration

    @property
    def synchronizer(self) -> MeshSynchronizer:
        return self._synchronizer

    @property
    def metrics(self) -> MeshMetrics:
        return self._metrics

    @property
    def telemetry(self) -> MeshTelemetry:
        return self._telemetry

    @property
    def health_service(self) -> MeshHealth:
        return self._health

    # Event handler
    async def _on_mesh_event(
        self, event: Dict[str, Any]
    ) -> None:
        self._telemetry.log_mesh_event(
            event.get("event_type", "unknown"),
            "event_bus",
            event,
        )

    # Bootstrap phase initializers
    def _init_configuration(self) -> Dict[str, Any]:
        self._context.set_config("mesh_initialized", True)
        self._configuration.apply_configuration(self._config)
        return {"success": True}

    def _init_discovery(self) -> Dict[str, Any]:
        return {"success": True}

    def _init_control_plane(self) -> Dict[str, Any]:
        return {"success": True}

    def _init_data_plane(self) -> Dict[str, Any]:
        return {"success": True}

    def _init_sidecar_runtime(self) -> Dict[str, Any]:
        return {"success": True}

    def _init_mesh_ready(self) -> Dict[str, Any]:
        self._lifecycle.transition_to(
            MeshState.RUNNING, "mesh_ready"
        )
        return {"success": True, "mesh_id": self._metadata.mesh_id}

    # Utility methods
    async def create_sidecar(
        self,
        sidecar_id: str,
        service_name: str,
        namespace: str = "default",
    ) -> Sidecar:
        """Create a sidecar for a business service."""
        self._metrics.increment_sidecar_total(
            {"service": service_name}
        )
        return await self._manager.create_sidecar(
            sidecar_id, service_name, namespace
        )

    async def handle_request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Handle a request through the mesh proxy."""
        self._metrics.increment_proxy_request(
            {"method": method, "path": path}
        )
        return await self._data_plane.intercept(
            method, path, headers
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "metadata": self._metadata.to_dict(),
            "running": self._started,
            "lifecycle": self._lifecycle.get_stats(),
            "bootstrap": self._bootstrap.get_stats(),
            "metrics": self._metrics.get_summary(),
            "health": self._health.get_stats(),
        }

    def __repr__(self) -> str:
        return (
            f"ServiceMesh(id={self._metadata.mesh_id}, "
            f"running={self._started})"
        )
