"""Factor Health Check — health monitoring for factor research components.

Monitors the health of factor engine, pipeline, feature store,
evaluation modules, and alpha pool.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Component health status."""

    UP = "UP"
    DOWN = "DOWN"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ComponentHealth:
    """Health status of a single component."""

    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    response_time_ms: float = 0.0


@dataclass
class HealthReport:
    """Aggregated health report."""

    status: HealthStatus = HealthStatus.UNKNOWN
    components: Dict[str, ComponentHealth] = field(default_factory=dict)
    uptime_seconds: float = 0.0
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "components": {
                name: {
                    "status": ch.status.value,
                    "details": ch.details,
                    "response_time_ms": ch.response_time_ms,
                }
                for name, ch in self.components.items()
            },
            "uptime_seconds": self.uptime_seconds,
            "checked_at": self.checked_at.isoformat(),
            "version": self.version,
        }


class FactorHealthCheck:
    """Health monitoring for factor research components.

    Checks:
    * Factor engine availability
    * Pipeline responsiveness
    * Feature store connectivity
    * Evaluation module health
    * Alpha pool state
    """

    def __init__(self) -> None:
        self._started_at = datetime.now(timezone.utc)
        self._lock = asyncio.Lock()

    @property
    def uptime_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self._started_at).total_seconds()

    async def check_health(
        self,
        context: Optional[Dict[str, Any]] = None,
    ) -> HealthReport:
        """Perform comprehensive health check.

        Args:
            context: optional component references

        Returns:
            HealthReport with all component statuses
        """
        context = context or {}
        report = HealthReport(
            uptime_seconds=self.uptime_seconds,
        )

        # Check each component
        report.components["factor_engine"] = await self._check_component(
            "factor_engine", context.get("engine")
        )
        report.components["factor_manager"] = await self._check_component(
            "factor_manager", context.get("manager")
        )
        report.components["pipeline"] = await self._check_component(
            "pipeline", context.get("pipeline")
        )
        report.components["feature_store"] = await self._check_component(
            "feature_store", context.get("feature_store")
        )
        report.components["alpha_pool"] = await self._check_component(
            "alpha_pool", context.get("alpha_pool")
        )

        # Aggregate status
        statuses = [c.status for c in report.components.values()]
        if all(s == HealthStatus.UP for s in statuses):
            report.status = HealthStatus.UP
        elif any(s == HealthStatus.DOWN for s in statuses):
            report.status = HealthStatus.DOWN
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            report.status = HealthStatus.DEGRADED
        else:
            report.status = HealthStatus.UNKNOWN

        logger.info("Health check: %s", report.status.value)
        return report

    async def _check_component(
        self, name: str, component: Any
    ) -> ComponentHealth:
        """Check health of a single component."""
        start = time.time()

        if component is None:
            return ComponentHealth(
                name=name,
                status=HealthStatus.UNKNOWN,
                details={"message": "Component not initialized"},
                response_time_ms=(time.time() - start) * 1000,
            )

        try:
            # Check if component has a state attribute
            if hasattr(component, "state"):
                state = component.state
                state_val = state.value if hasattr(state, "value") else str(state)
                status = HealthStatus.UP if state_val in ("ready", "running") else HealthStatus.DEGRADED
            else:
                status = HealthStatus.UP
                state_val = "available"

            # Get component stats if available
            details = {"state": state_val}
            if hasattr(component, "stats"):
                try:
                    s = component.stats
                    if callable(s):
                        details["stats"] = s()
                    else:
                        details["stats"] = s
                except Exception:
                    pass

            return ComponentHealth(
                name=name,
                status=status,
                details=details,
                response_time_ms=(time.time() - start) * 1000,
            )

        except Exception as exc:
            return ComponentHealth(
                name=name,
                status=HealthStatus.DOWN,
                details={"error": str(exc)},
                response_time_ms=(time.time() - start) * 1000,
            )

    async def quick_check(self) -> Dict[str, Any]:
        """Quick health check returning simple status."""
        report = await self.check_health()
        return {
            "status": report.status.value,
            "uptime_seconds": report.uptime_seconds,
        }

    async def liveness(self) -> bool:
        """Liveness probe — is the service alive?"""
        return True

    async def readiness(self, context: Optional[Dict[str, Any]] = None) -> bool:
        """Readiness probe — is the service ready to accept work?"""
        report = await self.check_health(context)
        return report.status in (HealthStatus.UP, HealthStatus.DEGRADED)
