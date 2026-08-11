"""
Control Plane Manager — Lifecycle coordination for Control Plane services.

Manages start/stop/restart of individual control plane engines and
handles dependency ordering.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    FAILED = "failed"


@dataclass
class ServiceInfo:
    name: str
    status: ServiceStatus = ServiceStatus.STOPPED
    instance: Any = None
    dependencies: list[str] = field(default_factory=list)
    started_at: float = 0.0
    error: Optional[str] = None


class ControlPlaneManager:
    """
    Manages the lifecycle of all Control Plane services/engines.

    Ensures proper startup ordering based on declared dependencies
    and provides health status for each service.
    """

    def __init__(self):
        self._services: dict[str, ServiceInfo] = {}
        self._startup_order: list[str] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        instance: Any,
        dependencies: Optional[list[str]] = None,
    ) -> None:
        """Register a control plane service."""
        self._services[name] = ServiceInfo(
            name=name,
            instance=instance,
            dependencies=dependencies or [],
        )
        logger.info("Registered service: %s (deps: %s)", name, dependencies)

    def unregister(self, name: str) -> None:
        """Remove a registered service."""
        self._services.pop(name, None)
        self._startup_order = [s for s in self._startup_order if s != name]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start_all(self) -> bool:
        """Start all registered services in dependency order."""
        try:
            self._startup_order = self._compute_startup_order()
        except ValueError as e:
            logger.error("Circular dependency detected: %s", e)
            return False

        for name in self._startup_order:
            success = await self._start_service(name)
            if not success:
                logger.critical("Failed to start %s — halting startup", name)
                return False

        logger.info("All %d services started successfully", len(self._startup_order))
        return True

    async def stop_all(self) -> None:
        """Stop all services in reverse dependency order."""
        for name in reversed(self._startup_order):
            await self._stop_service(name)
        self._startup_order = []

    async def restart_service(self, name: str) -> bool:
        """Restart a single service."""
        await self._stop_service(name)
        return await self._start_service(name)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _compute_startup_order(self) -> list[str]:
        """Topological sort based on declared dependencies."""
        visited: set[str] = set()
        temp_mark: set[str] = set()
        order: list[str] = []

        def visit(name: str):
            if name in temp_mark:
                raise ValueError(f"Circular dependency involving {name}")
            if name in visited:
                return
            temp_mark.add(name)
            if name in self._services:
                for dep in self._services[name].dependencies:
                    if dep in self._services:
                        visit(dep)
            temp_mark.discard(name)
            visited.add(name)
            order.append(name)

        for name in self._services:
            visit(name)

        return order

    async def _start_service(self, name: str) -> bool:
        info = self._services.get(name)
        if not info:
            return True

        if info.status == ServiceStatus.RUNNING:
            return True

        info.status = ServiceStatus.STARTING
        try:
            if hasattr(info.instance, "start"):
                await info.instance.start()
            info.status = ServiceStatus.RUNNING
            info.started_at = asyncio.get_event_loop().time()
            info.error = None
            logger.info("Service %s → RUNNING", name)
            return True
        except Exception as e:
            info.status = ServiceStatus.FAILED
            info.error = str(e)
            logger.exception("Service %s FAILED: %s", name, e)
            return False

    async def _stop_service(self, name: str) -> None:
        info = self._services.get(name)
        if not info or info.status != ServiceStatus.RUNNING:
            return
        info.status = ServiceStatus.STOPPING
        try:
            if hasattr(info.instance, "stop"):
                await info.instance.stop()
        except Exception:
            logger.exception("Error stopping service %s", name)
        info.status = ServiceStatus.STOPPED

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def service_status(self, name: str) -> Optional[ServiceInfo]:
        return self._services.get(name)

    def all_status(self) -> dict[str, dict]:
        return {
            name: {
                "status": info.status.value,
                "started_at": info.started_at,
                "error": info.error,
                "dependencies": info.dependencies,
            }
            for name, info in self._services.items()
        }

    @property
    def all_running(self) -> bool:
        return all(
            info.status == ServiceStatus.RUNNING
            for info in self._services.values()
        )
