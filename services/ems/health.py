"""EMS Health — Health check endpoints for the Execution Management System.

Provides liveness and readiness checks for the EMS components,
enabling Kubernetes-compatible health probes.

Checks:
    - Liveness: Is the EMS process alive?
    - Readiness: Is the EMS ready to accept execution tasks?
    - Component health: Are individual components healthy?

Usage::

    checker = EMSHealthChecker()
    liveness = await checker.check_liveness()
    readiness = await checker.check_readiness()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


@dataclass
class HealthCheckResult:
    """Result of a health check.

    Attributes:
        component: Component being checked
        status: Health status
        message: Status message
        details: Additional details
        checked_at: Check timestamp
        latency_ms: Check duration in ms
    """

    component: str = ""
    status: HealthStatus = HealthStatus.HEALTHY
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "checked_at": self.checked_at.isoformat(),
            "latency_ms": self.latency_ms,
        }


class EMSHealthChecker:
    """EMS health check provider.

    Provides liveness and readiness probes compatible with
    Kubernetes health check endpoints.

    Attributes:
        _engine_healthy: Whether the execution engine is healthy
        _scheduler_healthy: Whether the scheduler is healthy
        _dispatcher_healthy: Whether the dispatcher is healthy
        _last_check: Last health check timestamp
    """

    def __init__(self) -> None:
        self._engine_healthy = True
        self._scheduler_healthy = True
        self._dispatcher_healthy = True
        self._last_check: Optional[datetime] = None

    # ── Health Probes ──────────────────────────────────────────────

    async def check_liveness(self) -> HealthCheckResult:
        """Check if the EMS process is alive.

        Simple liveness probe — returns healthy if the process
        is running and responsive.

        Returns:
            HealthCheckResult
        """
        import time
        start = time.monotonic()

        self._last_check = datetime.now(timezone.utc)

        return HealthCheckResult(
            component="ems",
            status=HealthStatus.HEALTHY,
            message="EMS is alive",
            details={
                "last_check": self._last_check.isoformat(),
                "uptime": "available",
            },
            latency_ms=(time.monotonic() - start) * 1000,
        )

    async def check_readiness(self) -> HealthCheckResult:
        """Check if the EMS is ready to accept execution tasks.

        Verifies that all critical components are operational.

        Returns:
            HealthCheckResult
        """
        import time
        start = time.monotonic()

        all_healthy = all([
            self._engine_healthy,
            self._scheduler_healthy,
            self._dispatcher_healthy,
        ])

        if all_healthy:
            status = HealthStatus.HEALTHY
            message = "EMS is ready"
        elif any([self._engine_healthy, self._scheduler_healthy]):
            status = HealthStatus.DEGRADED
            message = "EMS is degraded — some components unhealthy"
        else:
            status = HealthStatus.UNHEALTHY
            message = "EMS is not ready — critical components unhealthy"

        return HealthCheckResult(
            component="ems",
            status=status,
            message=message,
            details={
                "engine": "healthy" if self._engine_healthy else "unhealthy",
                "scheduler": "healthy" if self._scheduler_healthy else "unhealthy",
                "dispatcher": "healthy" if self._dispatcher_healthy else "unhealthy",
            },
            latency_ms=(time.monotonic() - start) * 1000,
        )

    async def check_component(self, component_name: str) -> HealthCheckResult:
        """Check health of a specific component.

        Args:
            component_name: Name of the component to check

        Returns:
            HealthCheckResult
        """
        import time
        start = time.monotonic()

        healthy = True
        if component_name == "engine":
            healthy = self._engine_healthy
        elif component_name == "scheduler":
            healthy = self._scheduler_healthy
        elif component_name == "dispatcher":
            healthy = self._dispatcher_healthy

        return HealthCheckResult(
            component=component_name,
            status=HealthStatus.HEALTHY if healthy else HealthStatus.UNHEALTHY,
            message=f"Component {component_name} is {'healthy' if healthy else 'unhealthy'}",
            latency_ms=(time.monotonic() - start) * 1000,
        )

    async def full_health_check(self) -> dict[str, HealthCheckResult]:
        """Run full health check on all components.

        Returns:
            Dict of component name → HealthCheckResult
        """
        results = {}
        for component in ["engine", "scheduler", "dispatcher"]:
            results[component] = await self.check_component(component)
        return results

    # ── Status Updates ─────────────────────────────────────────────

    def set_engine_healthy(self, healthy: bool) -> None:
        """Update engine health status.

        Args:
            healthy: Whether engine is healthy
        """
        self._engine_healthy = healthy
        if not healthy:
            logger.warning("Engine health set to unhealthy")

    def set_scheduler_healthy(self, healthy: bool) -> None:
        """Update scheduler health status.

        Args:
            healthy: Whether scheduler is healthy
        """
        self._scheduler_healthy = healthy
        if not healthy:
            logger.warning("Scheduler health set to unhealthy")

    def set_dispatcher_healthy(self, healthy: bool) -> None:
        """Update dispatcher health status.

        Args:
            healthy: Whether dispatcher is healthy
        """
        self._dispatcher_healthy = healthy
        if not healthy:
            logger.warning("Dispatcher health set to unhealthy")

    def to_dict(self) -> dict[str, Any]:
        """Serialize health state."""
        return {
            "engine": "healthy" if self._engine_healthy else "unhealthy",
            "scheduler": "healthy" if self._scheduler_healthy else "unhealthy",
            "dispatcher": "healthy" if self._dispatcher_healthy else "unhealthy",
            "last_check": self._last_check.isoformat() if self._last_check else None,
        }
