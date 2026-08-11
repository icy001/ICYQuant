"""
Portfolio Health — Health status tracking for the portfolio risk platform.

Aggregates health signals from all portfolio subsystems and provides
a unified health assessment for monitoring and orchestration.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SubsystemHealth(str, Enum):
    """Individual subsystem health status."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class PortfolioHealthStatus(str, Enum):
    """Overall portfolio platform health."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    NOT_INITIALIZED = "NOT_INITIALIZED"


@dataclass
class SubsystemReport:
    """Health report for a single portfolio subsystem."""
    name: str
    status: SubsystemHealth = SubsystemHealth.UNKNOWN
    message: str = ""
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    consecutive_failures: int = 0
    max_consecutive_failures: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def circuit_open(self) -> bool:
        """Circuit breaker is open (subsystem considered unhealthy)."""
        return self.consecutive_failures >= self.max_consecutive_failures


@dataclass
class PortfolioHealthReport:
    """Aggregate health report for the portfolio platform."""
    overall_status: PortfolioHealthStatus = PortfolioHealthStatus.NOT_INITIALIZED
    subsystems: dict[str, SubsystemReport] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uptime_seconds: float = 0.0
    active_positions: int = 0
    total_equity: float = 0.0
    daily_pnl: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status.value,
            "subsystems": {
                name: {
                    "status": r.status.value,
                    "message": r.message,
                    "circuit_open": r.circuit_open,
                    "consecutive_failures": r.consecutive_failures,
                }
                for name, r in self.subsystems.items()
            },
            "generated_at": self.generated_at.isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "active_positions": self.active_positions,
            "total_equity": self.total_equity,
            "daily_pnl": self.daily_pnl,
        }


class PortfolioHealthMonitor:
    """
    Health monitoring for the entire portfolio risk platform.

    Aggregates health signals from all portfolio subsystems (PnL,
    exposure, margin, monitors, alerts, actions) and provides a
    unified health report for orchestration and monitoring.

    Usage::

        health = PortfolioHealthMonitor()
        await health.initialize()
        report = await health.check()
    """

    def __init__(self) -> None:
        self._subsystems: dict[str, Any] = {}
        self._reports: dict[str, SubsystemReport] = {}
        self._initialized = False
        self._startup_time: Optional[datetime] = None
        self._lock = asyncio.Lock()
        self._position_count: int = 0
        self._total_equity: float = 0.0
        self._daily_pnl: float = 0.0

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the health monitor."""
        self._initialized = True
        self._startup_time = datetime.now(timezone.utc)
        logger.info("PortfolioHealthMonitor initialized.")

    async def stop(self) -> None:
        """Stop the health monitor."""
        self._initialized = False
        logger.info("PortfolioHealthMonitor stopped.")

    # ---- Subsystem Registration ----

    def register_subsystem(self, name: str, instance: Any) -> None:
        """Register a subsystem for health monitoring."""
        self._subsystems[name] = instance
        self._reports[name] = SubsystemReport(name=name, status=SubsystemHealth.UNKNOWN)
        logger.info(f"Subsystem registered: {name}")

    def unregister_subsystem(self, name: str) -> None:
        """Remove a subsystem from health monitoring."""
        self._subsystems.pop(name, None)
        self._reports.pop(name, None)
        logger.info(f"Subsystem unregistered: {name}")

    # ---- Health Check ----

    async def check(self) -> PortfolioHealthReport:
        """
        Run a full health check across all registered subsystems.

        Returns a PortfolioHealthReport with aggregated status.
        """
        if not self._initialized:
            return PortfolioHealthReport()

        checks = []
        for name, subsystem in self._subsystems.items():
            checks.append(self._check_subsystem(name, subsystem))

        results = await asyncio.gather(*checks, return_exceptions=True)

        for i, (name, _) in enumerate(self._subsystems.items()):
            if isinstance(results[i], Exception):
                self._update_failure(name, str(results[i]))
            elif isinstance(results[i], SubsystemReport):
                self._reports[name] = results[i]

        # Determine overall status
        statuses = [r.status for r in self._reports.values()]
        if SubsystemHealth.UNHEALTHY in statuses:
            overall = PortfolioHealthStatus.UNHEALTHY
        elif SubsystemHealth.DEGRADED in statuses:
            overall = PortfolioHealthStatus.DEGRADED
        elif all(s == SubsystemHealth.HEALTHY for s in statuses):
            overall = PortfolioHealthStatus.HEALTHY
        else:
            overall = PortfolioHealthStatus.DEGRADED

        uptime = (
            (datetime.now(timezone.utc) - self._startup_time).total_seconds()
            if self._startup_time else 0.0
        )

        return PortfolioHealthReport(
            overall_status=overall,
            subsystems=dict(self._reports),
            uptime_seconds=uptime,
            active_positions=self._position_count,
            total_equity=self._total_equity,
            daily_pnl=self._daily_pnl,
        )

    # ---- Updates ----

    def update_portfolio_metrics(
        self,
        position_count: int = 0,
        total_equity: float = 0.0,
        daily_pnl: float = 0.0,
    ) -> None:
        """Update portfolio-level metrics for health reporting."""
        self._position_count = position_count
        self._total_equity = total_equity
        self._daily_pnl = daily_pnl

    # ---- Internal ----

    async def _check_subsystem(self, name: str, subsystem: Any) -> SubsystemReport:
        """Check health of a single subsystem."""
        existing = self._reports.get(name)
        try:
            if hasattr(subsystem, "health_check"):
                result = await subsystem.health_check()
                status_str = result.get("status", "unknown")
                if status_str in ("running", "healthy", "HEALTHY"):
                    return SubsystemReport(
                        name=name,
                        status=SubsystemHealth.HEALTHY,
                        message=f"{name} is healthy.",
                        consecutive_failures=0,
                        metadata=result,
                    )
                elif status_str in ("degraded", "DEGRADED"):
                    return SubsystemReport(
                        name=name,
                        status=SubsystemHealth.DEGRADED,
                        message=f"{name} is degraded.",
                        metadata=result,
                    )
                else:
                    return SubsystemReport(
                        name=name,
                        status=SubsystemHealth.UNHEALTHY,
                        message=f"{name} status: {status_str}",
                        metadata=result,
                    )
            else:
                return SubsystemReport(
                    name=name,
                    status=SubsystemHealth.HEALTHY,
                    message=f"{name} has no health_check method (assumed healthy).",
                )
        except Exception as e:
            failures = (existing.consecutive_failures + 1) if existing else 1
            status = (
                SubsystemHealth.UNHEALTHY if failures >= 3
                else SubsystemHealth.DEGRADED
            )
            return SubsystemReport(
                name=name,
                status=status,
                message=f"Health check failed: {e}",
                consecutive_failures=failures,
            )

    def _update_failure(self, name: str, error: str) -> None:
        """Update a subsystem as failed due to an exception."""
        existing = self._reports.get(name)
        failures = (existing.consecutive_failures + 1) if existing else 1
        self._reports[name] = SubsystemReport(
            name=name,
            status=SubsystemHealth.UNHEALTHY if failures >= 3 else SubsystemHealth.DEGRADED,
            message=f"Exception: {error}",
            consecutive_failures=failures,
        )
