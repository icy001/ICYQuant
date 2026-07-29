from services.monitoring.health.service_health import ServiceHealthMonitor, ServiceStatus, HealthReport
from services.monitoring.health.dependency_health import DependencyChecker, DependencyStatus
from services.monitoring.health.readiness import ReadinessProbe, ReadinessResult, ProbeType


# Backward-compatible HealthStatus (old: UP/DOWN/DEGRADED)
class HealthStatus:
    UP = "UP"
    DOWN = "DOWN"
    DEGRADED = "DEGRADED"


__all__ = [
    "ServiceHealthMonitor",
    "ServiceStatus",
    "HealthReport",
    "HealthStatus",
    "DependencyChecker",
    "DependencyStatus",
    "ReadinessProbe",
    "ReadinessResult",
    "ProbeType",
]
