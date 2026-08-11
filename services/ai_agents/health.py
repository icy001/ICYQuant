"""
ICYQuant Agent Health — health check probes for the multi-agent system.

Provides liveness, readiness, and startup probes compliant with
Kubernetes health check conventions for monitoring and orchestration.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    component: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    """Aggregate health report for the multi-agent system."""
    status: HealthStatus = HealthStatus.HEALTHY
    uptime_seconds: float = 0.0
    version: str = "0.4.0-alpha2"

    # Component health
    components: dict[str, ComponentHealth] = field(default_factory=dict)

    # Summary
    total_components: int = 0
    healthy_components: int = 0
    degraded_components: int = 0
    unhealthy_components: int = 0

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "uptime_seconds": self.uptime_seconds,
            "version": self.version,
            "components": {
                name: {
                    "status": ch.status.value,
                    "message": ch.message,
                    "latency_ms": ch.latency_ms,
                }
                for name, ch in self.components.items()
            },
            "summary": {
                "total": self.total_components,
                "healthy": self.healthy_components,
                "degraded": self.degraded_components,
                "unhealthy": self.unhealthy_components,
            },
            "timestamp": self.timestamp.isoformat(),
        }


class HealthProbe:
    """Health check probes for the multi-agent system.

    Probe types:
        - Liveness: Is the system running? (basic process check)
        - Readiness: Is the system ready to serve requests?
        - Startup: Has the system finished initializing?
    """

    def __init__(self, runtime: Any = None,
                 registry: Any = None,
                 communication_bus: Any = None,
                 shared_memory: Any = None) -> None:
        self._runtime = runtime
        self._registry = registry
        self._comm_bus = communication_bus
        self._shared_memory = shared_memory
        self._started_at = datetime.now(timezone.utc)
        self._initialized = False

    @property
    def uptime_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self._started_at).total_seconds()

    def mark_initialized(self) -> None:
        self._initialized = True

    # ── Liveness Probe ──

    async def liveness(self) -> HealthReport:
        """Check if the system is alive (basic process check)."""
        report = HealthReport(
            status=HealthStatus.HEALTHY,
            uptime_seconds=self.uptime_seconds,
        )

        components = {
            "runtime": self._check_runtime(),
            "registry": self._check_registry(),
            "communication_bus": self._check_comm_bus(),
            "shared_memory": self._check_memory(),
        }

        report.components = components
        report.total_components = len(components)

        for comp in components.values():
            comp_status = comp.status.value
            if comp_status == "healthy":
                report.healthy_components += 1
            elif comp_status == "degraded":
                report.degraded_components += 1
            else:
                report.unhealthy_components += 1

        if report.unhealthy_components > 1:
            report.status = HealthStatus.UNHEALTHY
        elif report.degraded_components > 0:
            report.status = HealthStatus.DEGRADED

        return report

    # ── Readiness Probe ──

    async def readiness(self) -> HealthReport:
        """Check if the system is ready to serve requests."""
        report = await self.liveness()

        if not self._initialized:
            report.status = HealthStatus.UNHEALTHY
            report.components["initialization"] = ComponentHealth(
                component="initialization",
                status=HealthStatus.UNHEALTHY,
                message="System not yet initialized",
            )

        # Check minimum agent count for readiness
        if self._registry:
            agent_count = getattr(self._registry, 'agent_count', 0)
            if agent_count < 1:
                report.status = HealthStatus.DEGRADED
                report.components["agent_count"] = ComponentHealth(
                    component="agent_count",
                    status=HealthStatus.DEGRADED,
                    message=f"Only {agent_count} agents registered",
                )

        return report

    # ── Startup Probe ──

    async def startup(self) -> HealthReport:
        """Check if the system has finished starting up."""
        report = HealthReport(
            uptime_seconds=self.uptime_seconds,
        )

        if self._initialized:
            report.status = HealthStatus.HEALTHY
        else:
            report.status = HealthStatus.UNHEALTHY
            report.components["startup"] = ComponentHealth(
                component="startup",
                status=HealthStatus.UNHEALTHY,
                message="System still starting up",
            )

        return report

    # ── Component Checks ──

    def _check_runtime(self) -> ComponentHealth:
        if self._runtime is None:
            return ComponentHealth(
                component="runtime",
                status=HealthStatus.HEALTHY,
                message="No runtime configured",
            )
        try:
            is_ready = getattr(self._runtime, 'is_ready', False)
            state = str(getattr(self._runtime, 'state', 'unknown'))
            if is_ready:
                return ComponentHealth(component="runtime", status=HealthStatus.HEALTHY, message=f"State: {state}")
            return ComponentHealth(component="runtime", status=HealthStatus.DEGRADED, message=f"State: {state}")
        except Exception as exc:
            return ComponentHealth(component="runtime", status=HealthStatus.UNHEALTHY, message=str(exc))

    def _check_registry(self) -> ComponentHealth:
        if self._registry is None:
            return ComponentHealth(
                component="registry",
                status=HealthStatus.HEALTHY,
                message="No registry configured",
            )
        try:
            count = getattr(self._registry, 'agent_count', 0)
            return ComponentHealth(
                component="registry",
                status=HealthStatus.HEALTHY,
                message=f"{count} agents registered",
            )
        except Exception as exc:
            return ComponentHealth(component="registry", status=HealthStatus.UNHEALTHY, message=str(exc))

    def _check_comm_bus(self) -> ComponentHealth:
        if self._comm_bus is None:
            return ComponentHealth(
                component="communication_bus",
                status=HealthStatus.HEALTHY,
                message="No communication bus configured",
            )
        try:
            agents = getattr(self._comm_bus, 'agent_count', 0)
            return ComponentHealth(
                component="communication_bus",
                status=HealthStatus.HEALTHY,
                message=f"{agents} connected agents",
            )
        except Exception as exc:
            return ComponentHealth(component="communication_bus", status=HealthStatus.UNHEALTHY, message=str(exc))

    def _check_memory(self) -> ComponentHealth:
        if self._shared_memory is None:
            return ComponentHealth(
                component="shared_memory",
                status=HealthStatus.HEALTHY,
                message="No shared memory configured",
            )
        try:
            size = getattr(self._shared_memory, 'total_size', 0)
            return ComponentHealth(
                component="shared_memory",
                status=HealthStatus.HEALTHY,
                message=f"{size} entries stored",
            )
        except Exception as exc:
            return ComponentHealth(component="shared_memory", status=HealthStatus.UNHEALTHY, message=str(exc))
