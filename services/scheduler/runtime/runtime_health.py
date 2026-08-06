"""Runtime Health Checker — monitors scheduler runtime health."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


class HealthStatus(str, enum.Enum):
    """Component health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Result of a single health check."""

    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    duration_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RuntimeHealthChecker:
    """Periodic health checker for the scheduler runtime.

    Runs a set of health checks against scheduler components and
    aggregates results into an overall health status.

    Usage::

        checker = RuntimeHealthChecker()
        checker.register("event_bus", lambda: check_bus())
        report = checker.run_all()
    """

    def __init__(self) -> None:
        self._checks: Dict[str, Any] = {}  # name → callable
        self._last_results: List[HealthCheck] = []

    def register(self, name: str, check_fn: Any) -> None:
        """Register a health check function."""
        self._checks[name] = check_fn

    def unregister(self, name: str) -> None:
        """Remove a health check."""
        self._checks.pop(name, None)

    def run_all(self) -> List[HealthCheck]:
        """Execute all registered health checks."""
        results: List[HealthCheck] = []
        for name, check_fn in self._checks.items():
            start = datetime.now(timezone.utc)
            try:
                detail = check_fn()
                status = HealthStatus.HEALTHY
                message = "OK"
                if isinstance(detail, dict) and "status" in detail:
                    status = HealthStatus(detail["status"])
                    message = detail.get("message", "OK")
                elif isinstance(detail, HealthStatus):
                    status = detail
                check = HealthCheck(
                    name=name,
                    status=status,
                    message=message,
                    duration_ms=(
                        datetime.now(timezone.utc) - start
                    ).total_seconds() * 1000,
                    details=detail if isinstance(detail, dict) else {},
                )
            except Exception as exc:
                check = HealthCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(exc),
                    duration_ms=(
                        datetime.now(timezone.utc) - start
                    ).total_seconds() * 1000,
                )
            results.append(check)
        self._last_results = results
        return results

    def overall_status(self) -> HealthStatus:
        """Aggregate the overall health status from last run."""
        if not self._last_results:
            return HealthStatus.UNKNOWN
        statuses = [r.status for r in self._last_results]
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        if any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        return HealthStatus.UNKNOWN

    def health_report(self) -> Dict[str, Any]:
        """Produce a comprehensive health report."""
        self.run_all()
        return {
            "overall": self.overall_status().value,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "duration_ms": c.duration_ms,
                    "details": c.details,
                    "checked_at": c.checked_at.isoformat() if c.checked_at else None,
                }
                for c in self._last_results
            ],
        }
