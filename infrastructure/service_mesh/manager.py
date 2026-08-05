"""Mesh Manager for the Service Mesh.

Provides ``MeshManager`` for unified management of the mesh
lifecycle, sidecars, configuration, and synchronization.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .bootstrap import BootstrapPhase, MeshBootstrap
from .context import MeshContext
from .control_plane import ControlPlane
from .data_plane import DataPlane
from .events import MeshEvent, MeshEventPublisher
from .lifecycle import MeshLifecycle, MeshState
from .models import MeshMetadata, ProxyConfig, ProxyType
from .runtime import MeshRuntime
from .sidecar import Sidecar
from .exceptions import MeshRuntimeError

logger = logging.getLogger(__name__)


class MeshManager:
    """Unified manager for the service mesh."""

    def __init__(
        self,
        context: Optional[MeshContext] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or MeshContext()
        self._metadata = MeshMetadata()
        self._publisher = MeshEventPublisher()
        self._lifecycle = MeshLifecycle()
        self._bootstrap = MeshBootstrap(
            self._context, self._lifecycle
        )
        self._runtime = MeshRuntime(self._context)
        self._control_plane = ControlPlane(self._context)
        self._data_plane = DataPlane(self._context)
        self._sidecars: Dict[str, Sidecar] = {}
        self._mesh_config: Dict[str, Any] = {}
        self._created = False
        self._running = False

        # Wire publisher
        self._runtime.set_publisher(self._publisher)
        self._control_plane.set_publisher(self._publisher)
        self._data_plane.set_publisher(self._publisher)
        self._bootstrap.set_publisher(self._publisher)

        # Register components in context
        self._context.register("mesh_manager", self)
        self._context.register("metadata", self._metadata)

        # Register default bootstrap phases
        self._bootstrap.register_phase(
            BootstrapPhase.CONFIGURATION,
            self._init_configuration,
        )
        self._bootstrap.register_phase(
            BootstrapPhase.SERVICE_DISCOVERY,
            self._init_service_discovery,
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

    async def create_mesh(
        self,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create and bootstrap the service mesh."""
        if self._created:
            return {
                "success": False,
                "error": "Mesh already created",
            }

        if config:
            self._mesh_config = config
            self._context.set_config("mesh_config", config)

        self._created = True
        result = await self._bootstrap.startup()

        if result.get("bootstrapped"):
            self._running = True
            await self._runtime.start(self._mesh_config)
            logger.info("Service mesh created successfully.")
        else:
            self._created = False
            logger.error(
                "Service mesh creation failed: %s",
                result.get("failed_phase"),
            )

        return result

    async def destroy_mesh(self) -> Dict[str, Any]:
        """Destroy and shutdown the service mesh."""
        if not self._created:
            return {
                "success": False,
                "error": "Mesh not created",
            }

        # Stop sidecars
        for sidecar_id in list(self._sidecars.keys()):
            try:
                await self._sidecars[sidecar_id].stop()
            except Exception as exc:
                logger.warning(
                    "Error stopping sidecar %s: %s",
                    sidecar_id,
                    exc,
                )

        self._sidecars.clear()

        # Stop data plane and control plane
        await self._data_plane.stop()
        await self._control_plane.stop()
        await self._runtime.stop()

        self._running = False
        self._created = False
        self._lifecycle.transition_to(
            MeshState.STOPPED, "mesh_destroyed"
        )

        await self._publisher.publish(MeshEvent.MESH_STOPPED)

        logger.info("Service mesh destroyed.")
        return {"success": True}

    async def create_sidecar(
        self,
        sidecar_id: str,
        service_name: str,
        namespace: str = "default",
        proxy_type: ProxyType = ProxyType.INTERNAL,
    ) -> Sidecar:
        """Create a new sidecar for a business service."""
        if sidecar_id in self._sidecars:
            return self._sidecars[sidecar_id]

        sidecar = Sidecar(
            sidecar_id=sidecar_id,
            service_name=service_name,
            namespace=namespace,
            proxy_type=proxy_type,
            context=self._context,
        )
        sidecar.set_publisher(self._publisher)
        await sidecar.start()
        self._sidecars[sidecar_id] = sidecar

        logger.info(
            "Sidecar %s created for service %s.",
            sidecar_id,
            service_name,
        )
        return sidecar

    async def destroy_sidecar(self, sidecar_id: str) -> Dict[str, Any]:
        """Destroy a sidecar."""
        if sidecar_id not in self._sidecars:
            return {
                "success": False,
                "error": f"Sidecar {sidecar_id} not found",
            }

        sidecar = self._sidecars.pop(sidecar_id)
        return await sidecar.stop()

    def get_sidecar(self, sidecar_id: str) -> Optional[Sidecar]:
        return self._sidecars.get(sidecar_id)

    def list_sidecars(
        self, service_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        result = []
        for sc in self._sidecars.values():
            info = sc.get_instance().to_dict()
            if service_name is None or info["service_name"] == service_name:
                result.append(info)
        return result

    async def reload(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Reload the mesh with new configuration."""
        return await self._runtime.reload(config)

    # Bootstrap phase initializers
    def _init_configuration(self) -> Dict[str, Any]:
        self._context.set_config("initialized", True)
        return {"success": True, "phase": "configuration"}

    def _init_service_discovery(self) -> Dict[str, Any]:
        return {"success": True, "phase": "service_discovery"}

    def _init_control_plane(self) -> Dict[str, Any]:
        return {"success": True, "phase": "control_plane"}

    def _init_data_plane(self) -> Dict[str, Any]:
        return {"success": True, "phase": "data_plane"}

    def _init_sidecar_runtime(self) -> Dict[str, Any]:
        return {"success": True, "phase": "sidecar_runtime"}

    def _init_mesh_ready(self) -> Dict[str, Any]:
        return {"success": True, "phase": "mesh_ready", "mesh_id": self._metadata.mesh_id}

    def get_mesh_info(self) -> Dict[str, Any]:
        return {
            "metadata": self._metadata.to_dict(),
            "created": self._created,
            "running": self._running,
            "sidecar_count": len(self._sidecars),
            "lifecycle": self._lifecycle.get_stats(),
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "mesh": self.get_mesh_info(),
            "bootstrap": self._bootstrap.get_stats(),
            "runtime": self._runtime.get_stats(),
            "control_plane": self._control_plane.get_stats(),
            "data_plane": self._data_plane.get_stats(),
            "sidecars": {
                sid: sc.get_stats()
                for sid, sc in self._sidecars.items()
            },
            "publisher": self._publisher.get_stats(),
        }

    def __repr__(self) -> str:
        return (
            f"MeshManager(created={self._created}, "
            f"running={self._running}, "
            f"sidecars={len(self._sidecars)})"
        )
