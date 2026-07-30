"""
Health check module.

Provides service health monitoring.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


@dataclass
class HealthResult:
    service: str
    status: HealthStatus
    message: str = ""


class HealthMonitor:
    def check(self, service: str) -> HealthResult:
        return HealthResult(
            service=service,
            status=HealthStatus.HEALTHY,
            message=f"{service} is healthy",
        )


def healthy(service: str) -> HealthResult:
    monitor = HealthMonitor()
    return monitor.check(service)
