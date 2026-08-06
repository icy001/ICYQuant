"""Runtime Health — health checking and diagnostics for research runtimes.

Monitors runtime environment health, detects anomalies, and provides
diagnostic information for troubleshooting.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(str, Enum):
    """Types of components being checked."""

    ENVIRONMENT = "environment"
    SCHEDULER = "scheduler"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    CACHE = "cache"
    GPU = "gpu"


@dataclass
class HealthCheckResult:
    """Result of a single health check."""

    component: str = ""
    component_type: ComponentType = ComponentType.ENVIRONMENT
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    latency_ms: float = 0.0
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "component_type": self.component_type.value,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "details": self.details,
            "checked_at": self.checked_at.isoformat(),
        }


@dataclass
class HealthReport:
    """Aggregated health report across all runtime components."""

    status: HealthStatus = HealthStatus.UNKNOWN
    checks: List[HealthCheckResult] = field(default_factory=list)
    total_checks: int = 0
    healthy_count: int = 0
    degraded_count: int = 0
    unhealthy_count: int = 0
    total_latency_ms: float = 0.0
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uptime_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_result(self, result: HealthCheckResult) -> None:
        self.checks.append(result)
        self.total_checks += 1
        if result.status == HealthStatus.HEALTHY:
            self.healthy_count += 1
        elif result.status == HealthStatus.DEGRADED:
            self.degraded_count += 1
        elif result.status == HealthStatus.UNHEALTHY:
            self.unhealthy_count += 1
        self.total_latency_ms += result.latency_ms

    def finalize(self) -> None:
        if self.unhealthy_count > 0:
            self.status = HealthStatus.UNHEALTHY
        elif self.degraded_count > 0:
            self.status = HealthStatus.DEGRADED
        else:
            self.status = HealthStatus.HEALTHY

    def unhealthy_components(self) -> List[HealthCheckResult]:
        return [c for c in self.checks if c.status == HealthStatus.UNHEALTHY]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "checks": [c.to_dict() for c in self.checks],
            "total_checks": self.total_checks,
            "healthy": self.healthy_count,
            "degraded": self.degraded_count,
            "unhealthy": self.unhealthy_count,
            "total_latency_ms": self.total_latency_ms,
            "generated_at": self.generated_at.isoformat(),
            "uptime_seconds": self.uptime_seconds,
        }

    def __repr__(self) -> str:
        return (
            f"HealthReport(status={self.status.value}, "
            f"healthy={self.healthy_count}/{self.total_checks})"
        )


class RuntimeHealth:
    """Health monitoring and diagnostics for research runtimes.

    Periodically checks component health, detects degradation,
    and provides diagnostic reports for troubleshooting.

    Usage::

        health = RuntimeHealth()
        health.register_check("scheduler", check_scheduler_health)
        health.register_check("storage", check_storage_health)
        report = await health.run_checks()
    """

    def __init__(self) -> None:
        self._checks: Dict[str, Callable[..., HealthCheckResult]] = {}
        self._check_metadata: Dict[str, Dict[str, Any]] = {}
        self._start_time: float = time.monotonic()
        self._last_report: Optional[HealthReport] = None

    @property
    def uptime_seconds(self) -> float:
        return time.monotonic() - self._start_time

    def register_check(
        self,
        name: str,
        check_fn: Callable[..., HealthCheckResult],
        component_type: ComponentType = ComponentType.ENVIRONMENT,
        interval_seconds: int = 30,
    ) -> None:
        """Register a health check function.

        Args:
            name: Unique check name.
            check_fn: Async callable returning HealthCheckResult.
            component_type: Type of component being checked.
            interval_seconds: Recommended check interval.
        """
        self._checks[name] = check_fn
        self._check_metadata[name] = {
            "component_type": component_type,
            "interval_seconds": interval_seconds,
        }

    def unregister(self, name: str) -> bool:
        return self._checks.pop(name, None) is not None

    async def run_check(self, name: str) -> HealthCheckResult:
        """Run a single registered health check."""
        check_fn = self._checks.get(name)
        if check_fn is None:
            return HealthCheckResult(
                component=name,
                status=HealthStatus.UNKNOWN,
                message=f"Check '{name}' not registered",
            )
        start = time.monotonic()
        try:
            result = check_fn()
            if asyncio.iscoroutine(result):
                result = await result
            result.latency_ms = (time.monotonic() - start) * 1000
            return result
        except Exception as exc:
            return HealthCheckResult(
                component=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {exc}",
                error=str(exc),
                latency_ms=(time.monotonic() - start) * 1000,
            )

    async def run_checks(self) -> HealthReport:
        """Run all registered health checks and return a report."""
        report = HealthReport(uptime_seconds=self.uptime_seconds)
        for name in self._checks:
            result = await self.run_check(name)
            meta = self._check_metadata.get(name, {})
            result.component_type = meta.get("component_type", ComponentType.ENVIRONMENT)
            report.add_result(result)
        report.finalize()
        self._last_report = report
        return report

    async def is_healthy(self) -> bool:
        report = await self.run_checks()
        return report.status == HealthStatus.HEALTHY

    def last_report(self) -> Optional[HealthReport]:
        return self._last_report

    def registered_checks(self) -> List[str]:
        return list(self._checks.keys())

    def __repr__(self) -> str:
        return f"RuntimeHealth(checks={len(self._checks)}, uptime={self.uptime_seconds:.0f}s)"
