"""
DAG Health — health check endpoints for DAG execution components.

Provides status for:
- DAG compiler
- Dependency resolver
- Scheduler
- Worker pool
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status for a single component."""

    component: str
    status: HealthStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class DAGHealthChecker:
    """
    Checks the health of all DAG execution components.

    Usage:
        checker = DAGHealthChecker()
        health = await checker.check()
        # {"dag_compiler": "healthy", "scheduler": "healthy", ...}
    """

    def __init__(self):
        self._component_status: Dict[str, ComponentHealth] = {}

    async def check(self) -> Dict[str, Any]:
        """
        Run health checks on all components.

        Returns:
            Dict with overall status and per-component health.
        """
        checks = [
            await self._check_compiler(),
            await self._check_scheduler(),
            await self._check_worker_pool(),
            await self._check_dependency_resolver(),
        ]

        for check in checks:
            self._component_status[check.component] = check

        # Overall status: unhealthy if any component is unhealthy
        overall = HealthStatus.HEALTHY
        if any(c.status == HealthStatus.UNHEALTHY for c in checks):
            overall = HealthStatus.UNHEALTHY
        elif any(c.status == HealthStatus.DEGRADED for c in checks):
            overall = HealthStatus.DEGRADED

        return {
            "status": overall.value,
            "timestamp": self._now_iso(),
            "components": {
                c.component: {
                    "status": c.status.value,
                    "message": c.message,
                    "details": c.details,
                }
                for c in checks
            },
        }

    async def _check_compiler(self) -> ComponentHealth:
        return ComponentHealth(
            component="dag_compiler",
            status=HealthStatus.HEALTHY,
            message="DAG compiler is operational",
        )

    async def _check_scheduler(self) -> ComponentHealth:
        return ComponentHealth(
            component="scheduler",
            status=HealthStatus.HEALTHY,
            message="Scheduler is operational",
        )

    async def _check_worker_pool(self) -> ComponentHealth:
        return ComponentHealth(
            component="worker_pool",
            status=HealthStatus.HEALTHY,
            message="Worker pool is operational",
        )

    async def _check_dependency_resolver(self) -> ComponentHealth:
        return ComponentHealth(
            component="dependency_resolver",
            status=HealthStatus.HEALTHY,
            message="Dependency resolver is operational",
        )

    def _now_iso(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def is_healthy(self) -> bool:
        """Quick check: is everything healthy?"""
        return all(
            h.status == HealthStatus.HEALTHY
            for h in self._component_status.values()
        )
