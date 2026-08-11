"""
ICYQuant Data Platform Health — health check and circuit breaker.

Monitors all data platform subsystems and provides readiness/liveness
probes for orchestration systems.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"


@dataclass
class ComponentHealth:
    name: str
    status: HealthStatus
    message: str = ""
    last_checked: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class DataPlatformHealthChecker:
    """Health check for all data platform components.

    Monitored components:
        - Connectivity
        - Normalization
        - Streaming
        - Data Lake
        - Governance
        - API Gateway
        - Pipeline
    """

    def __init__(self) -> None:
        self._components: dict[str, ComponentHealth] = {}
        self._overall_status = HealthStatus.STARTING

    def check_all(self) -> dict[str, str]:
        """Check all components."""
        import time
        now = time.time()

        results: dict[str, str] = {}
        for name, component in self._components.items():
            component.last_checked = now
            results[name] = component.status.value

        statuses = [c.status for c in self._components.values()]
        if HealthStatus.UNHEALTHY in statuses:
            self._overall_status = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            self._overall_status = HealthStatus.DEGRADED
        else:
            self._overall_status = HealthStatus.HEALTHY

        return results

    def set_component_health(
        self,
        name: str,
        status: HealthStatus,
        message: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        import time
        self._components[name] = ComponentHealth(
            name=name,
            status=status,
            message=message,
            last_checked=time.time(),
            metadata=metadata or {},
        )

    def get_component_health(self, name: str) -> Optional[ComponentHealth]:
        return self._components.get(name)

    def is_healthy(self) -> bool:
        return self._overall_status == HealthStatus.HEALTHY

    def is_ready(self) -> bool:
        """Readiness probe."""
        return self._overall_status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)

    def is_alive(self) -> bool:
        """Liveness probe."""
        return self._overall_status != HealthStatus.UNHEALTHY

    def get_readiness_response(self) -> dict[str, Any]:
        return {
            "status": "ready" if self.is_ready() else "not_ready",
            "overall": self._overall_status.value,
            "components": {name: c.status.value for name, c in self._components.items()},
        }

    def get_liveness_response(self) -> dict[str, Any]:
        return {
            "status": "alive" if self.is_alive() else "dead",
            "overall": self._overall_status.value,
        }

    @property
    def overall_status(self) -> HealthStatus:
        return self._overall_status

    @property
    def component_count(self) -> int:
        return len(self._components)
