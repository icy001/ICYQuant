"""
Portfolio Health — Health probe system for portfolio risk platform.

Provides liveness, readiness, and startup probes with circuit
breaker pattern for fault-tolerant operation in Kubernetes
and other orchestration environments.
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
    """Component health status."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    STARTING = "STARTING"
    STOPPING = "STOPPING"


class ProbeType(str, Enum):
    """Health probe types."""
    LIVENESS = "LIVENESS"
    READINESS = "READINESS"
    STARTUP = "STARTUP"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    component: str
    status: HealthStatus = HealthStatus.HEALTHY
    message: str = ""
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    consecutive_failures: int = 0
    max_consecutive_failures: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def circuit_open(self) -> bool:
        return self.consecutive_failures >= self.max_consecutive_failures


@dataclass
class PortfolioHealthReport:
    """Aggregate health report for the portfolio platform."""
    status: HealthStatus = HealthStatus.STARTING
    probe_type: ProbeType = ProbeType.LIVENESS
    components: dict[str, ComponentHealth] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uptime_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "probe_type": self.probe_type.value,
            "components": {
                name: {
                    "status": c.status.value,
                    "message": c.message,
                    "circuit_open": c.circuit_open,
                    "consecutive_failures": c.consecutive_failures,
                }
                for name, c in self.components.items()
            },
            "generated_at": self.generated_at.isoformat(),
            "uptime_seconds": self.uptime_seconds,
        }


class PortfolioHealthChecker:
    """
    Health probe system for the portfolio risk platform.

    Provides Kubernetes-compatible liveness, readiness, and startup
    probes with circuit breaker pattern for fault-tolerant operation.

    Usage::

        checker = PortfolioHealthChecker()
        await checker.initialize()

        checker.register("pnl_engine", pnl_engine)
        checker.register("exposure_engine", exposure_engine)

        liveness = await checker.liveness_probe()
        readiness = await checker.readiness_probe()
    """

    def __init__(self) -> None:
        self._components: dict[str, Any] = {}
        self._health: dict[str, ComponentHealth] = {}
        self._startup_time: Optional[datetime] = None
        self._initialized = False
        self._ready = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the health checker."""
        self._initialized = True
        self._startup_time = datetime.now(timezone.utc)
        logger.info("PortfolioHealthChecker initialized.")

    async def mark_ready(self) -> None:
        """Mark the platform as ready to serve traffic."""
        self._ready = True
        logger.info("PortfolioHealthChecker: platform marked as READY.")

    # ---- Registration ----

    def register(self, name: str, component: Any) -> None:
        """Register a component for health checking."""
        self._components[name] = component
        self._health[name] = ComponentHealth(component=name)
        logger.debug(f"Health component registered: {name}")

    def unregister(self, name: str) -> None:
        """Remove a component from health checking."""
        self._components.pop(name, None)
        self._health.pop(name, None)

    # ---- Probes ----

    async def liveness_probe(self) -> PortfolioHealthReport:
        """
        Liveness probe — is the application alive?

        Checks basic health of all registered components.
        Returns UNHEALTHY if any critical component has failed.
        """
        return await self._run_probe(ProbeType.LIVENESS, critical_only=True)

    async def readiness_probe(self) -> PortfolioHealthReport:
        """
        Readiness probe — is the application ready to serve traffic?

        Checks that all components are initialized and healthy.
        Returns UNHEALTHY if not ready or any component is unhealthy.
        """
        if not self._ready:
            return PortfolioHealthReport(
                status=HealthStatus.STARTING,
                probe_type=ProbeType.READINESS,
                metadata={"message": "Platform not yet ready"},
            )
        return await self._run_probe(ProbeType.READINESS)

    async def startup_probe(self) -> PortfolioHealthReport:
        """
        Startup probe — has the application started successfully?

        Checks that all components have completed initialization.
        """
        if not self._initialized:
            return PortfolioHealthReport(
                status=HealthStatus.STARTING,
                probe_type=ProbeType.STARTUP,
                metadata={"message": "Platform still starting"},
            )

        report = await self._run_probe(ProbeType.STARTUP)
        return report

    # ---- Manual Health Updates ----

    def set_component_health(
        self,
        name: str,
        status: HealthStatus,
        message: str = "",
    ) -> None:
        """Manually set health status for a component."""
        if name in self._health:
            comp = self._health[name]
            comp.status = status
            comp.message = message
            comp.last_checked = datetime.now(timezone.utc)

            if status == HealthStatus.UNHEALTHY:
                comp.consecutive_failures += 1
            elif status == HealthStatus.HEALTHY:
                comp.consecutive_failures = 0

    # ---- Query ----

    def get_uptime(self) -> float:
        """Get platform uptime in seconds."""
        if not self._startup_time:
            return 0.0
        return (datetime.now(timezone.utc) - self._startup_time).total_seconds()

    # ---- Internal ----

    async def _run_probe(
        self,
        probe_type: ProbeType,
        critical_only: bool = False,
    ) -> PortfolioHealthReport:
        """Run a health probe across components."""
        import time

        for name, component in self._components.items():
            comp = self._health.get(name)
            if not comp:
                continue

            try:
                if hasattr(component, "health_check"):
                    result = await component.health_check()
                    status_str = result.get("status", "unknown")

                    if status_str in ("healthy", "running", "HEALTHY"):
                        comp.status = HealthStatus.HEALTHY
                        comp.consecutive_failures = 0
                    elif status_str in ("degraded", "DEGRADED"):
                        comp.status = HealthStatus.DEGRADED
                    else:
                        comp.status = HealthStatus.UNHEALTHY
                        comp.consecutive_failures += 1

                    comp.message = result.get("message", str(result))
                    comp.metadata = result
                else:
                    comp.status = HealthStatus.HEALTHY
                    comp.message = "No health check — assumed healthy"

                comp.last_checked = datetime.now(timezone.utc)

            except Exception as e:
                comp.status = HealthStatus.UNHEALTHY
                comp.consecutive_failures += 1
                comp.message = f"Health check failed: {e}"

        # Aggregate
        unhealthy = 0
        degraded = 0
        for comp in self._health.values():
            if comp.circuit_open:
                unhealthy += 1
            elif comp.status == HealthStatus.UNHEALTHY:
                unhealthy += 1
            elif comp.status == HealthStatus.DEGRADED:
                degraded += 1

        if unhealthy > 0:
            overall = HealthStatus.UNHEALTHY
        elif degraded > 0:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        return PortfolioHealthReport(
            status=overall,
            probe_type=probe_type,
            components=dict(self._health),
            uptime_seconds=self.get_uptime(),
        )
