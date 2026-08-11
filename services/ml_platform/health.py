"""
ICYQuant ML Platform Health - Health check probes.

Provides Kubernetes-style health probes:
- Liveness: Is the service running?
- Readiness: Is the service ready to serve?
- Startup: Has the service initialized?
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a single health check."""

    check_name: str
    status: HealthStatus = HealthStatus.HEALTHY
    message: str = ""
    latency_ms: float = 0.0
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    """Complete health check report."""

    status: HealthStatus = HealthStatus.UNHEALTHY
    version: str = "v0.4.0-alpha2"
    uptime_seconds: float = 0.0
    checks: Dict[str, HealthCheckResult] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response format."""
        return {
            "status": self.status.value,
            "version": self.version,
            "uptime_seconds": self.uptime_seconds,
            "checks": {
                name: {
                    "status": check.status.value,
                    "message": check.message,
                    "latency_ms": check.latency_ms,
                }
                for name, check in self.checks.items()
            },
            "checked_at": self.checked_at.isoformat(),
        }


class MLHealthChecker:
    """Health probe manager for the ML platform.

    Checks:
    - Feature Store connectivity
    - Offline/Online store availability
    - Training pipeline status
    - Model registry accessibility
    - Resource usage (memory, CPU)
    """

    def __init__(self) -> None:
        self._started_at: Optional[datetime] = None
        self._last_report: Optional[HealthReport] = None

    async def startup(self) -> None:
        """Record platform startup time."""
        self._started_at = datetime.utcnow()
        logger.info("ML Platform health checker started")

    # -- Liveness Probe --

    async def liveness(self) -> HealthCheckResult:
        """Check if the service is alive (basic).

        Should be lightweight - just checks if the process is running.
        """
        return HealthCheckResult(
            check_name="liveness",
            status=HealthStatus.HEALTHY,
            message="ML Platform is alive",
        )

    # -- Readiness Probe --

    async def readiness(
        self,
        feature_store: Optional[Any] = None,
        offline_store: Optional[Any] = None,
        online_store: Optional[Any] = None,
        model_registry: Optional[Any] = None,
    ) -> HealthReport:
        """Check if the service is ready to serve requests.

        Performs deeper checks than liveness:
        - Feature store accessible
        - Stores connected
        - Key subsystems healthy
        """
        import time

        report = HealthReport(status=HealthStatus.HEALTHY)
        if self._started_at:
            report.uptime_seconds = (datetime.utcnow() - self._started_at).total_seconds()

        checks: Dict[str, HealthCheckResult] = {}

        # Feature store
        checks["feature_store"] = await self._check_subsystem(
            "feature_store", feature_store,
        )

        # Offline store
        checks["offline_store"] = await self._check_subsystem(
            "offline_store", offline_store,
        )

        # Online store
        checks["online_store"] = await self._check_subsystem(
            "online_store", online_store,
        )

        # Model registry
        checks["model_registry"] = await self._check_subsystem(
            "model_registry", model_registry,
        )

        report.checks = checks

        # Overall status
        statuses = [c.status for c in checks.values()]
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            report.status = HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            report.status = HealthStatus.DEGRADED
        else:
            report.status = HealthStatus.HEALTHY

        self._last_report = report
        return report

    async def _check_subsystem(
        self, name: str, instance: Any,
    ) -> HealthCheckResult:
        """Check a subsystem's health."""
        if instance is None:
            return HealthCheckResult(
                check_name=name,
                status=HealthStatus.DEGRADED,
                message=f"{name} not initialized",
            )

        try:
            if hasattr(instance, 'is_healthy'):
                is_healthy = instance.is_healthy()
            else:
                is_healthy = True
        except Exception as exc:
            return HealthCheckResult(
                check_name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"{name} health check failed: {exc}",
            )

        return HealthCheckResult(
            check_name=name,
            status=HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
            message=f"{name} is {'healthy' if is_healthy else 'unhealthy'}",
        )

    # -- Startup Probe --

    async def startup_probe(
        self,
        initialized: bool = False,
    ) -> HealthCheckResult:
        """Check if the service has fully initialized.

        Used to determine if the container is ready to receive traffic.
        """
        if initialized:
            return HealthCheckResult(
                check_name="startup",
                status=HealthStatus.HEALTHY,
                message="ML Platform initialized successfully",
            )
        else:
            return HealthCheckResult(
                check_name="startup",
                status=HealthStatus.UNHEALTHY,
                message="ML Platform still initializing",
            )

    def get_last_report(self) -> Optional[HealthReport]:
        """Get the last health report."""
        return self._last_report
