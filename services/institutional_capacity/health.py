"""
Capacity Health Checker — Component-level health checks and uptime tracking.

Monitors the operational health of all capacity management components:
strategy capacity, liquidity, execution, impact, portfolio, and decisions.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a single capacity component."""

    component_id: str = field(default_factory=lambda: f"CH-{uuid.uuid4().hex[:8]}")
    name: str = ""
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    startup_time: float = field(default_factory=time.time)
    last_check_time: float = 0.0
    uptime_seconds: float = 0.0
    check_count: int = 0
    error_count: int = 0
    last_error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        return self.status == HealthStatus.HEALTHY

    @property
    def error_rate(self) -> float:
        if self.check_count == 0:
            return 0.0
        return self.error_count / self.check_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "check_count": self.check_count,
            "error_count": self.error_count,
            "error_rate": round(self.error_rate, 4),
            "last_error": self.last_error,
            "metadata": self.metadata,
        }


@dataclass
class SystemHealth:
    """Aggregated health of all capacity components."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    components: Dict[str, ComponentHealth] = field(default_factory=dict)
    overall_status: HealthStatus = HealthStatus.UNKNOWN

    @property
    def healthy_components(self) -> int:
        return sum(1 for c in self.components.values() if c.status == HealthStatus.HEALTHY)

    @property
    def degraded_components(self) -> int:
        return sum(1 for c in self.components.values() if c.status == HealthStatus.DEGRADED)

    @property
    def unhealthy_components(self) -> int:
        return sum(1 for c in self.components.values() if c.status == HealthStatus.UNHEALTHY)

    @property
    def is_all_healthy(self) -> bool:
        return self.overall_status == HealthStatus.HEALTHY

    @property
    def total_components(self) -> int:
        return len(self.components)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "overall_status": self.overall_status.value,
            "total_components": self.total_components,
            "healthy": self.healthy_components,
            "degraded": self.degraded_components,
            "unhealthy": self.unhealthy_components,
            "is_all_healthy": self.is_all_healthy,
            "components": {k: v.to_dict() for k, v in self.components.items()},
        }


class CapacityHealthChecker:
    """Component health checker for capacity management.

    Supports: registration, periodic health checks, liveness/readiness probes.
    """

    # Component names
    COMPONENT_CAPACITY_INTELLIGENCE = "capacity_intelligence"
    COMPONENT_CAPACITY_MANAGER = "capacity_manager"
    COMPONENT_CAPACITY_ORCHESTRATOR = "capacity_orchestrator"
    COMPONENT_LIQUIDITY = "liquidity"
    COMPONENT_EXECUTION = "execution"
    COMPONENT_IMPACT = "impact"
    COMPONENT_PORTFOLIO = "portfolio"
    COMPONENT_DECISIONS = "decisions"
    COMPONENT_GUARD = "guard"
    COMPONENT_METRICS = "metrics"
    COMPONENT_TELEMETRY = "telemetry"

    def __init__(self):
        self._components: Dict[str, ComponentHealth] = {}
        self._health_checks: Dict[str, Callable[[], Tuple[HealthStatus, str]]] = {}

        # Register default components
        for name in [
            self.COMPONENT_CAPACITY_INTELLIGENCE,
            self.COMPONENT_CAPACITY_MANAGER,
            self.COMPONENT_CAPACITY_ORCHESTRATOR,
            self.COMPONENT_LIQUIDITY,
            self.COMPONENT_EXECUTION,
            self.COMPONENT_IMPACT,
            self.COMPONENT_PORTFOLIO,
            self.COMPONENT_DECISIONS,
            self.COMPONENT_GUARD,
            self.COMPONENT_METRICS,
            self.COMPONENT_TELEMETRY,
        ]:
            self._components[name] = ComponentHealth(
                name=name,
                status=HealthStatus.HEALTHY,
                message="Initialized",
            )

    # ── Registration ──────────────────────────────────────────────

    def register_component(self, name: str) -> None:
        if name not in self._components:
            self._components[name] = ComponentHealth(
                name=name,
                status=HealthStatus.HEALTHY,
                message="Registered",
            )

    def set_health_check(self, component_name: str,
                          check_fn: Callable[[], Tuple[HealthStatus, str]]) -> None:
        """Register a health check function for a component."""
        self.register_component(component_name)
        self._health_checks[component_name] = check_fn

    # ── Status Updates ────────────────────────────────────────────

    def set_healthy(self, component_name: str, message: str = "") -> None:
        self._update_component(component_name, HealthStatus.HEALTHY, message)

    def set_degraded(self, component_name: str, message: str = "") -> None:
        self._update_component(component_name, HealthStatus.DEGRADED, message)

    def set_unhealthy(self, component_name: str, message: str = "") -> None:
        self._update_component(component_name, HealthStatus.UNHEALTHY, message)

    def _update_component(self, name: str, status: HealthStatus, message: str) -> None:
        comp = self._components.get(name)
        if comp is None:
            comp = ComponentHealth(name=name)
            self._components[name] = comp

        comp.status = status
        if message:
            comp.message = message
        comp.last_check_time = time.time()
        comp.uptime_seconds = time.time() - comp.startup_time
        comp.check_count += 1

        if status != HealthStatus.HEALTHY:
            comp.error_count += 1
            comp.last_error = message

    def set_metadata(self, component_name: str, key: str, value: Any) -> None:
        comp = self._components.get(component_name)
        if comp:
            comp.metadata[key] = value

    # ── Health Check ──────────────────────────────────────────────

    def check_component(self, component_name: str) -> HealthStatus:
        """Run the health check for a single component."""
        check_fn = self._health_checks.get(component_name)
        if check_fn is None:
            return self._components.get(component_name, ComponentHealth()).status

        try:
            status, message = check_fn()
            self._update_component(component_name, status, message)
            return status
        except Exception as e:
            self._update_component(component_name, HealthStatus.UNHEALTHY, str(e))
            return HealthStatus.UNHEALTHY

    def check_all(self) -> SystemHealth:
        """Run all registered health checks and return system health."""
        for name in self._components:
            self.check_component(name)

        return self.system_health()

    def system_health(self) -> SystemHealth:
        """Get current system health snapshot."""

        # Determine overall status
        statuses = [c.status for c in self._components.values()]
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall = HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            overall = HealthStatus.DEGRADED
        elif all(s == HealthStatus.HEALTHY for s in statuses):
            overall = HealthStatus.HEALTHY
        else:
            overall = HealthStatus.UNKNOWN

        return SystemHealth(
            components=self._components.copy(),
            overall_status=overall,
        )

    # ── Liveness / Readiness Probes ────────────────────────────────

    def liveness(self) -> Tuple[bool, str]:
        """Kubernetes liveness probe: is the service alive?"""
        return True, "alive"

    def readiness(self) -> Tuple[bool, str]:
        """Kubernetes readiness probe: can the service accept requests?"""
        health = self.system_health()
        if health.overall_status == HealthStatus.UNHEALTHY:
            return False, f"not ready: {health.unhealthy_components} unhealthy components"
        return True, "ready"

    def startup(self) -> Tuple[bool, str]:
        """Kubernetes startup probe: has the service started?"""
        health = self.system_health()
        unknown = [
            name for name, c in health.components.items()
            if c.status == HealthStatus.UNKNOWN and c.check_count == 0
        ]
        if unknown:
            return False, f"starting: {len(unknown)} components not yet checked"
        return True, "started"

    # ── Queries ───────────────────────────────────────────────────

    def get_component(self, name: str) -> Optional[ComponentHealth]:
        return self._components.get(name)

    def unhealthy_components(self) -> List[ComponentHealth]:
        return [c for c in self._components.values() if c.status == HealthStatus.UNHEALTHY]

    def degraded_components(self) -> List[ComponentHealth]:
        return [c for c in self._components.values() if c.status == HealthStatus.DEGRADED]

    def component_names(self) -> List[str]:
        return list(self._components.keys())

    def uptime(self, component_name: str) -> float:
        comp = self._components.get(component_name)
        if comp is None:
            return 0.0
        return time.time() - comp.startup_time

    # ── Reset ─────────────────────────────────────────────────────

    def reset(self) -> None:
        for comp in self._components.values():
            comp.status = HealthStatus.HEALTHY
            comp.message = "Reset"
            comp.startup_time = time.time()
            comp.error_count = 0
            comp.last_error = ""

    def summary(self) -> Dict[str, Any]:
        health = self.system_health()
        return {
            "overall": health.overall_status.value,
            "is_healthy": health.is_all_healthy,
            "total_components": health.total_components,
            "healthy": health.healthy_components,
            "degraded": health.degraded_components,
            "unhealthy": health.unhealthy_components,
            "components": {
                name: {
                    "status": c.status.value,
                    "uptime": round(c.uptime_seconds, 1),
                    "error_rate": round(c.error_rate, 4),
                }
                for name, c in self._components.items()
            },
        }
