"""Unified health check framework."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class HealthComponent:
    name: str
    status: HealthStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    checked_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "latency_ms": self.latency_ms,
            "checked_at": self.checked_at.isoformat(),
        }

class HealthChecker:
    """Manages health checks for all platform components."""

    def __init__(self):
        self._checks: Dict[str, Callable[[], HealthComponent]] = {}
        self._component_status: Dict[str, HealthStatus] = {}

    def register(self, name: str, check_fn: Callable[[], HealthComponent]) -> None:
        self._checks[name] = check_fn
        self._component_status[name] = HealthStatus.HEALTHY

    def unregister(self, name: str) -> None:
        self._checks.pop(name, None)
        self._component_status.pop(name, None)

    def check(self, name: str) -> HealthComponent:
        fn = self._checks.get(name)
        if not fn:
            return HealthComponent(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"No health check registered for {name}",
            )
        try:
            component = fn()
            self._component_status[name] = component.status
            return component
        except Exception as e:
            self._component_status[name] = HealthStatus.UNHEALTHY
            return HealthComponent(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )

    def check_all(self) -> List[HealthComponent]:
        results = []
        for name in self._checks:
            results.append(self.check(name))
        return results

    def get_overall_status(self) -> HealthStatus:
        if not self._checks:
            return HealthStatus.HEALTHY
        statuses = list(self._component_status.values())
        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        return HealthStatus.DEGRADED

    def is_ready(self) -> bool:
        return self.get_overall_status() != HealthStatus.UNHEALTHY

    def get_status(self) -> dict:
        components = [c.to_dict() for c in self.check_all()]
        return {
            "status": self.get_overall_status().value,
            "ready": self.is_ready(),
            "components": components,
            "total": len(components),
            "healthy": sum(1 for c in components if c["status"] == "healthy"),
        }

    def __contains__(self, name: str) -> bool:
        return name in self._checks
