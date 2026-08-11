"""Lifecycle Health — Health check and monitoring endpoint.

Provides health status for all lifecycle engine subsystems:
- Engine status
- Event store health
- Metrics availability
- Handler status
- Audit trail status
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from services.oms.lifecycle.lifecycle_engine import LifecycleEngine
from services.oms.lifecycle.lifecycle_event_store import LifecycleEventStore
from services.oms.lifecycle.lifecycle_audit import LifecycleAudit
from services.oms.lifecycle.metrics import LifecycleMetrics
from services.oms.lifecycle.diagnostics import LifecycleDiagnostics, DiagnosticsReport

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Overall health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class SubsystemHealth:
    """Health status of a single subsystem."""
    name: str
    status: HealthStatus = HealthStatus.HEALTHY
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class HealthReport:
    """Comprehensive health report."""
    status: HealthStatus = HealthStatus.HEALTHY
    subsystems: list[SubsystemHealth] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uptime_seconds: float = 0.0
    version: str = "0.4.0-alpha2"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "status": self.status.value,
            "subsystems": [s.to_dict() for s in self.subsystems],
            "timestamp": self.timestamp.isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "version": self.version,
        }


class LifecycleHealth:
    """Health check provider for lifecycle engine.

    Monitors all lifecycle subsystems and provides a unified
    health status suitable for Kubernetes liveness/readiness probes.

    Usage::

        health = LifecycleHealth(engine, event_store, audit, metrics, diagnostics)
        report = await health.check()
        if report.status == HealthStatus.HEALTHY:
            # Service is healthy
        else:
            # Investigate subsystem reports
    """

    def __init__(
        self,
        engine: LifecycleEngine,
        event_store: LifecycleEventStore,
        audit: LifecycleAudit,
        metrics: LifecycleMetrics,
        diagnostics: LifecycleDiagnostics,
    ) -> None:
        self._engine = engine
        self._event_store = event_store
        self._audit = audit
        self._metrics = metrics
        self._diagnostics = diagnostics
        self._start_time: Optional[datetime] = None

    def mark_started(self) -> None:
        """Record the start time for uptime tracking."""
        self._start_time = datetime.now(timezone.utc)

    async def check(self) -> HealthReport:
        """Run a comprehensive health check.

        Returns:
            HealthReport with all subsystem statuses
        """
        subsystems: list[SubsystemHealth] = []

        # Check engine
        subsystems.append(self._check_engine())

        # Check event store
        subsystems.append(self._check_event_store())

        # Check audit
        subsystems.append(self._check_audit())

        # Check metrics
        subsystems.append(self._check_metrics())

        # Check diagnostics
        subsystems.append(await self._check_diagnostics())

        # Determine overall status
        statuses = [s.status for s in subsystems]
        if HealthStatus.UNHEALTHY in statuses:
            overall = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        # Calculate uptime
        uptime = 0.0
        if self._start_time:
            uptime = (
                datetime.now(timezone.utc) - self._start_time
            ).total_seconds()

        return HealthReport(
            status=overall,
            subsystems=subsystems,
            uptime_seconds=uptime,
        )

    def _check_engine(self) -> SubsystemHealth:
        """Check engine health."""
        engine_status = self._engine.status.value
        if engine_status == "running":
            return SubsystemHealth(
                name="lifecycle_engine",
                status=HealthStatus.HEALTHY,
                message="Engine is running",
            )
        elif engine_status in ("degraded", "initializing"):
            return SubsystemHealth(
                name="lifecycle_engine",
                status=HealthStatus.DEGRADED,
                message=f"Engine is {engine_status}",
            )
        else:
            return SubsystemHealth(
                name="lifecycle_engine",
                status=HealthStatus.UNHEALTHY,
                message=f"Engine is {engine_status}",
            )

    def _check_event_store(self) -> SubsystemHealth:
        """Check event store health."""
        store_dict = self._event_store.to_dict()
        return SubsystemHealth(
            name="event_store",
            status=HealthStatus.HEALTHY,
            message=f"Event store operational",
            details=store_dict,
        )

    def _check_audit(self) -> SubsystemHealth:
        """Check audit trail health."""
        audit_dict = self._audit.to_dict()
        return SubsystemHealth(
            name="lifecycle_audit",
            status=HealthStatus.HEALTHY,
            message="Audit trail active",
            details=audit_dict,
        )

    def _check_metrics(self) -> SubsystemHealth:
        """Check metrics health."""
        snapshot = self._metrics.snapshot()
        return SubsystemHealth(
            name="metrics",
            status=HealthStatus.HEALTHY,
            message="Metrics collection active",
            details={
                "events_total": snapshot.lifecycle_events_total,
                "transitions_total": snapshot.transition_total,
            },
        )

    async def _check_diagnostics(self) -> SubsystemHealth:
        """Check diagnostics health."""
        try:
            quick = await self._diagnostics.quick_health()
            if quick.get("healthy", False):
                return SubsystemHealth(
                    name="diagnostics",
                    status=HealthStatus.HEALTHY,
                    message="Diagnostics healthy",
                    details=quick,
                )
            return SubsystemHealth(
                name="diagnostics",
                status=HealthStatus.DEGRADED,
                message="Diagnostics found issues",
                details=quick,
            )
        except Exception as e:
            return SubsystemHealth(
                name="diagnostics",
                status=HealthStatus.DEGRADED,
                message=f"Diagnostics error: {e}",
            )

    async def liveness(self) -> dict[str, Any]:
        """Liveness probe — minimal check, is the service alive?

        Returns:
            Simple liveness status
        """
        return {
            "alive": self._engine.status.value != "stopped",
            "status": self._engine.status.value,
        }

    async def readiness(self) -> dict[str, Any]:
        """Readiness probe — is the service ready to accept work?

        Returns:
            Readiness status
        """
        report = await self.check()
        return {
            "ready": report.status == HealthStatus.HEALTHY,
            "status": report.status.value,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize health state."""
        return {
            "start_time": self._start_time.isoformat() if self._start_time else None,
        }
