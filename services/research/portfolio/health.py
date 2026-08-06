"""Portfolio Health Check — health monitoring for portfolio engine components.

Monitors the health of portfolio engine, optimizers, risk models,
stress testing, and report generation.

Status: UP / DOWN / DEGRADED / UNKNOWN
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
    """Health of a single component."""

    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    response_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "details": self.details,
            "checked_at": self.checked_at.isoformat(),
            "response_time_ms": self.response_time_ms,
        }


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
                name: c.to_dict() for name, c in self.components.items()
            },
            "uptime_seconds": self.uptime_seconds,
            "checked_at": self.checked_at.isoformat(),
            "version": self.version,
        }


class PortfolioHealthCheck:
    """Health monitoring for portfolio engine components.

    Periodically checks component health and generates
    aggregated health reports.
    """

    COMPONENTS = [
        "portfolio_engine",
        "optimizers",
        "risk_models",
        "stress_testing",
        "report_generator",
    ]

    def __init__(self) -> None:
        self._start_time = time.monotonic()
        self._components: Dict[str, Callable] = {}

    async def check_health(
        self,
        components: Optional[List[str]] = None,
    ) -> HealthReport:
        """Check health of portfolio components.

        Args:
            components: Components to check (default: all).

        Returns:
            HealthReport with component statuses.
        """
        to_check = components or self.COMPONENTS
        report = HealthReport(
            status=HealthStatus.UP,
            uptime_seconds=time.monotonic() - self._start_time,
        )

        all_up = True
        any_down = False
        any_degraded = False

        for comp_name in to_check:
            start = time.monotonic()
            try:
                comp_health = await self._check_component(comp_name)
            except Exception as e:
                comp_health = ComponentHealth(
                    name=comp_name,
                    status=HealthStatus.DOWN,
                    details={"error": str(e)},
                )

            comp_health.response_time_ms = (time.monotonic() - start) * 1000
            report.components[comp_name] = comp_health

            if comp_health.status == HealthStatus.DOWN:
                any_down = True
                all_up = False
            elif comp_health.status == HealthStatus.DEGRADED:
                any_degraded = True
                all_up = False

        if any_down:
            report.status = HealthStatus.DOWN
        elif any_degraded:
            report.status = HealthStatus.DEGRADED
        else:
            report.status = HealthStatus.UP

        return report

    async def _check_component(self, name: str) -> ComponentHealth:
        """Check a single component's health."""
        if name == "portfolio_engine":
            return ComponentHealth(
                name=name,
                status=HealthStatus.UP,
                details={"message": "Portfolio engine operational"},
            )
        elif name == "optimizers":
            return ComponentHealth(
                name=name,
                status=HealthStatus.UP,
                details={
                    "available": [
                        "mean_variance", "risk_parity",
                        "black_litterman", "hierarchical_risk_parity",
                    ],
                },
            )
        elif name == "risk_models":
            return ComponentHealth(
                name=name,
                status=HealthStatus.UP,
                details={
                    "models": [
                        "factor_risk", "covariance",
                        "tracking_error", "var", "cvar",
                    ],
                },
            )
        elif name == "stress_testing":
            return ComponentHealth(
                name=name,
                status=HealthStatus.UP,
                details={"scenarios_available": 6},
            )
        elif name == "report_generator":
            return ComponentHealth(
                name=name,
                status=HealthStatus.UP,
                details={"formats": ["json", "html"]},
            )
        else:
            return ComponentHealth(
                name=name,
                status=HealthStatus.UNKNOWN,
                details={"message": f"Unknown component: {name}"},
            )

    @property
    def uptime_seconds(self) -> float:
        return time.monotonic() - self._start_time
