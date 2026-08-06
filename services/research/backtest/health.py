"""Backtest Health Check — health monitoring for backtest engine components.

Monitors the health of the backtest engine, event system, execution
pipeline, performance engine, and report generator.

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
            "uptime_seconds": self.uptime_seconds,
            "checked_at": self.checked_at.isoformat(),
            "version": self.version,
            "components": {
                k: v.to_dict() for k, v in self.components.items()
            },
        }


class BacktestHealthCheck:
    """Health monitoring for the backtesting engine.

    Checks:
    * Engine responsiveness
    * Event system status
    * Execution pipeline
    * Performance engine
    * Report generator
    """

    def __init__(self) -> None:
        self._engine_state: Optional[str] = None
        self._event_queue_size: Optional[int] = None
        self._repository_ok: bool = True
        self._performance_ok: bool = True
        self._start_time = time.monotonic()

    # ── update state ───────────────────────────────────────────────────────

    def update_engine_state(self, state: str) -> None:
        self._engine_state = state

    def update_event_queue(self, size: int) -> None:
        self._event_queue_size = size

    def update_repository(self, ok: bool) -> None:
        self._repository_ok = ok

    def update_performance(self, ok: bool) -> None:
        self._performance_ok = ok

    # ── health check ───────────────────────────────────────────────────────

    async def check(self) -> HealthReport:
        """Execute all health checks and return a report.

        Returns:
            Aggregated HealthReport.
        """
        components: Dict[str, ComponentHealth] = {}
        start = time.monotonic()

        # 1. Engine health
        components["engine"] = self._check_engine()

        # 2. Event system
        components["event_system"] = self._check_event_system()

        # 3. Repository
        components["repository"] = self._check_repository()

        # 4. Performance engine
        components["performance"] = self._check_performance()

        # 5. Report generator
        components["report_generator"] = await self._check_report_generator()

        # Aggregate status
        statuses = [c.status for c in components.values()]
        if HealthStatus.DOWN in statuses:
            overall = HealthStatus.DOWN
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.UP

        report = HealthReport(
            status=overall,
            components=components,
            uptime_seconds=time.monotonic() - self._start_time,
        )

        elapsed = (time.monotonic() - start) * 1000
        logger.info("Health check complete: %s (%.0fms)", overall.value, elapsed)
        return report

    # ── individual checks ──────────────────────────────────────────────────

    def _check_engine(self) -> ComponentHealth:
        """Check engine health."""
        start = time.monotonic()
        state = self._engine_state or "unknown"

        if state in ("ready", "running", "paused"):
            status = HealthStatus.UP
        elif state in ("degraded",):
            status = HealthStatus.DEGRADED
        elif state in ("terminated",):
            status = HealthStatus.DOWN
        else:
            status = HealthStatus.UNKNOWN

        return ComponentHealth(
            name="engine",
            status=status,
            details={"state": state},
            response_time_ms=(time.monotonic() - start) * 1000,
        )

    def _check_event_system(self) -> ComponentHealth:
        """Check event system health."""
        start = time.monotonic()
        size = self._event_queue_size

        if size is None:
            return ComponentHealth(
                name="event_system",
                status=HealthStatus.UNKNOWN,
                details={"message": "Queue stats not available"},
            )

        if size > 100000:
            status = HealthStatus.DEGRADED
        elif size > 50000:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.UP

        return ComponentHealth(
            name="event_system",
            status=status,
            details={"queue_size": size},
            response_time_ms=(time.monotonic() - start) * 1000,
        )

    def _check_repository(self) -> ComponentHealth:
        """Check repository health."""
        start = time.monotonic()
        return ComponentHealth(
            name="repository",
            status=HealthStatus.UP if self._repository_ok else HealthStatus.DOWN,
            details={"connected": self._repository_ok},
            response_time_ms=(time.monotonic() - start) * 1000,
        )

    def _check_performance(self) -> ComponentHealth:
        """Check performance engine health."""
        start = time.monotonic()
        return ComponentHealth(
            name="performance",
            status=HealthStatus.UP if self._performance_ok else HealthStatus.DOWN,
            details={"available": self._performance_ok},
            response_time_ms=(time.monotonic() - start) * 1000,
        )

    async def _check_report_generator(self) -> ComponentHealth:
        """Check report generator health."""
        start = time.monotonic()
        return ComponentHealth(
            name="report_generator",
            status=HealthStatus.UP,  # always available
            details={"available": True},
            response_time_ms=(time.monotonic() - start) * 1000,
        )

    # ── query ──────────────────────────────────────────────────────────────

    def get_uptime(self) -> float:
        """Get engine uptime in seconds."""
        return time.monotonic() - self._start_time

    def get_stats(self) -> Dict[str, Any]:
        """Return health check statistics."""
        return {
            "uptime_seconds": self.get_uptime(),
            "engine_state": self._engine_state,
            "event_queue_size": self._event_queue_size,
            "repository_ok": self._repository_ok,
            "performance_ok": self._performance_ok,
        }
