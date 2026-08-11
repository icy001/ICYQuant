"""RiskHealth — health check endpoints for the risk subsystem.

Provides Kubernetes-style liveness/readiness probes and
health status for the capital risk subsystem.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class HealthStatus(Enum):
    HEALTHY = auto()
    DEGRADED = auto()
    UNHEALTHY = auto()


@dataclass
class ComponentHealth:
    """Health status of a single component."""

    name: str
    status: HealthStatus = HealthStatus.HEALTHY
    message: str = "OK"
    last_check: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    """Full health report."""

    overall: HealthStatus = HealthStatus.HEALTHY
    components: Dict[str, ComponentHealth] = field(default_factory=dict)
    uptime_seconds: float = 0.0
    timestamp: float = 0.0
    version: str = "0.1.0"


class RiskHealthChecker:
    """Health check for the risk subsystem.

    Provides:
    - Liveness probe: is the subsystem alive?
    - Readiness probe: is it ready to serve?
    - Component-level health

    Usage::

        checker = RiskHealthChecker()
        checker.start()
        # ...
        if checker.is_healthy():
            print("Risk subsystem healthy")
        report = checker.get_health_report()
    """

    def __init__(self):
        self._start_time: float = 0.0
        self._components: Dict[str, ComponentHealth] = {
            "risk_engine": ComponentHealth(name="Risk Engine"),
            "var_engine": ComponentHealth(name="VaR Engine"),
            "stress_engine": ComponentHealth(name="Stress Engine"),
            "survival_model": ComponentHealth(name="Survival Model"),
            "risk_budget": ComponentHealth(name="Risk Budget"),
            "guards": ComponentHealth(name="Risk Guards"),
            "telemetry": ComponentHealth(name="Telemetry"),
            "memory": ComponentHealth(name="Risk Memory"),
        }
        self._last_snapshot_time: float = 0.0
        self._snapshot_count: int = 0

    def start(self) -> None:
        """Mark subsystem as started."""
        self._start_time = time.time()

    @property
    def uptime(self) -> float:
        if self._start_time == 0:
            return 0.0
        return time.time() - self._start_time

    def is_healthy(self) -> bool:
        """Quick health check."""
        report = self.get_health_report()
        return report.overall == HealthStatus.HEALTHY

    def is_ready(self) -> bool:
        """Readiness check (all critical components healthy)."""
        critical = ["risk_engine", "var_engine", "survival_model"]
        for name in critical:
            comp = self._components.get(name)
            if comp and comp.status != HealthStatus.HEALTHY:
                return False
        # also check snapshot freshness
        if self._snapshot_count == 0:
            return False
        return True

    def update_component(
        self,
        name: str,
        status: HealthStatus,
        message: str = "",
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update a component's health status."""
        if name in self._components:
            comp = self._components[name]
            comp.status = status
            comp.message = message or ("OK" if status == HealthStatus.HEALTHY else "Error")
            comp.last_check = time.time()
            if metrics:
                comp.metrics.update(metrics)

    def record_snapshot(self) -> None:
        """Record that a risk snapshot was taken."""
        self._last_snapshot_time = time.time()
        self._snapshot_count += 1

    def get_health_report(self) -> HealthReport:
        """Get full health report."""
        now = time.time()

        # determine overall from components
        overall = HealthStatus.HEALTHY
        for comp in self._components.values():
            if comp.status == HealthStatus.UNHEALTHY:
                overall = HealthStatus.UNHEALTHY
                break
            elif comp.status == HealthStatus.DEGRADED:
                overall = HealthStatus.DEGRADED

        # check snapshot staleness
        if self._last_snapshot_time > 0 and (now - self._last_snapshot_time) > 60:
            overall = HealthStatus.DEGRADED

        return HealthReport(
            overall=overall,
            components=dict(self._components),
            uptime_seconds=self.uptime,
            timestamp=now,
        )

    def get_readiness(self) -> Dict[str, Any]:
        """Get readiness probe response."""
        ready = self.is_ready()
        return {
            "ready": ready,
            "uptime_seconds": self.uptime,
            "snapshot_count": self._snapshot_count,
            "last_snapshot_age_seconds": (
                time.time() - self._last_snapshot_time
                if self._last_snapshot_time > 0 else -1
            ),
        }

    def get_liveness(self) -> Dict[str, Any]:
        """Get liveness probe response."""
        return {
            "alive": True,
            "uptime_seconds": self.uptime,
        }
