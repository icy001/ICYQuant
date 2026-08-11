"""Allocation Health — Kubernetes-style health probes.

Provides:
- Liveness probe: is the allocation engine running?
- Readiness probe: is the system ready to process allocations?
- Component health status for all sub-systems
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class HealthStatus(str, Enum):
    """Component health status."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    STARTING = "STARTING"
    STOPPED = "STOPPED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    component_name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    uptime_seconds: float = 0.0
    last_checked: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    """Complete health report for the allocation system."""
    status: HealthStatus = HealthStatus.UNKNOWN
    components: Dict[str, ComponentHealth] = field(default_factory=dict)
    liveness: bool = False
    readiness: bool = False
    uptime_seconds: float = 0.0
    start_time: datetime = field(default_factory=datetime.utcnow)
    last_checked: datetime = field(default_factory=datetime.utcnow)
    version: str = "0.4.0-alpha2"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "liveness": self.liveness,
            "readiness": self.readiness,
            "uptime_seconds": self.uptime_seconds,
            "version": self.version,
            "components": {
                name: {
                    "status": comp.status.value,
                    "uptime_seconds": comp.uptime_seconds,
                    "error_count": comp.error_count,
                }
                for name, comp in self.components.items()
            },
        }


class AllocationHealth:
    """Health checker for the autonomous allocation system.

    Provides liveness/readiness probes for orchestration (K8s).
    """

    # Required components for readiness
    REQUIRED_COMPONENTS = [
        "allocation_engine",
        "allocation_runtime",
        "capacity_check",
        "liquidity_check",
        "guard_system",
        "feedback_system",
    ]

    # Required components for liveness
    LIVENESS_COMPONENTS = [
        "allocation_engine",
        "allocation_runtime",
        "guard_system",
    ]

    def __init__(self):
        self._start_time = datetime.utcnow()
        self._components: Dict[str, ComponentHealth] = {}
        self._init_components()

    def _init_components(self) -> None:
        """Initialize all component health statuses."""
        all_components = [
            "allocation_engine", "allocation_runtime", "allocation_manager",
            "allocation_controller", "allocation_orchestrator",
            "capacity_check", "liquidity_check", "risk_check",
            "guard_system", "rebalance_engine",
            "feedback_system", "metrics_collector",
        ]
        for name in all_components:
            self._components[name] = ComponentHealth(
                component_name=name,
                status=HealthStatus.STARTING,
                last_checked=datetime.utcnow(),
            )

    @property
    def uptime_seconds(self) -> float:
        return (datetime.utcnow() - self._start_time).total_seconds()

    def component_healthy(self, component_name: str,
                          metadata: Optional[Dict[str, Any]] = None) -> None:
        """Report a component as healthy."""
        if component_name in self._components:
            comp = self._components[component_name]
            comp.status = HealthStatus.HEALTHY
            comp.last_checked = datetime.utcnow()
            comp.uptime_seconds = self.uptime_seconds
            if metadata:
                comp.metadata.update(metadata)

    def component_error(self, component_name: str,
                        error: str) -> None:
        """Report a component error."""
        if component_name in self._components:
            comp = self._components[component_name]
            comp.status = HealthStatus.DEGRADED
            comp.last_error = error
            comp.error_count += 1
            comp.last_checked = datetime.utcnow()
            if comp.error_count > 5:
                comp.status = HealthStatus.UNHEALTHY

    def component_unhealthy(self, component_name: str,
                            reason: str = "") -> None:
        """Mark a component as unhealthy."""
        if component_name in self._components:
            comp = self._components[component_name]
            comp.status = HealthStatus.UNHEALTHY
            comp.last_error = reason
            comp.last_checked = datetime.utcnow()

    def component_stopped(self, component_name: str) -> None:
        """Mark a component as stopped."""
        if component_name in self._components:
            comp = self._components[component_name]
            comp.status = HealthStatus.STOPPED
            comp.last_checked = datetime.utcnow()

    def check_liveness(self) -> bool:
        """Check if the allocation system is alive.

        Returns True if all liveness-critical components are healthy.
        """
        for name in self.LIVENESS_COMPONENTS:
            comp = self._components.get(name)
            if not comp or comp.status in (HealthStatus.UNHEALTHY, HealthStatus.STOPPED):
                return False
        return True

    def check_readiness(self) -> bool:
        """Check if the system is ready to process allocations.

        Returns True if all required components are healthy.
        """
        for name in self.REQUIRED_COMPONENTS:
            comp = self._components.get(name)
            if not comp or comp.status not in (HealthStatus.HEALTHY, HealthStatus.DEGRADED):
                return False
        return True

    def check(self) -> HealthReport:
        """Generate a complete health report."""
        is_live = self.check_liveness()
        is_ready = self.check_readiness()

        # Determine overall status
        if not is_live:
            overall = HealthStatus.UNHEALTHY
        elif not is_ready:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        return HealthReport(
            status=overall,
            components=dict(self._components),
            liveness=is_live,
            readiness=is_ready,
            uptime_seconds=self.uptime_seconds,
            start_time=self._start_time,
            last_checked=datetime.utcnow(),
        )

    def get_liveness_response(self) -> Dict[str, Any]:
        """K8s liveness probe response."""
        is_live = self.check_liveness()
        return {
            "status": "alive" if is_live else "dead",
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_readiness_response(self) -> Dict[str, Any]:
        """K8s readiness probe response."""
        is_ready = self.check_readiness()
        return {
            "status": "ready" if is_ready else "not_ready",
            "timestamp": datetime.utcnow().isoformat(),
        }

    def reset(self) -> None:
        """Reset all health statuses."""
        self._start_time = datetime.utcnow()
        self._init_components()
