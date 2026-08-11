"""
Health check integration for the AI Agent Platform.

Provides component-level and aggregate health status reporting
for integration with ICYQuant platform health monitoring.

Checks:
    - Agent Runtime status
    - Engine pipeline health
    - Memory subsystem health
    - Session manager capacity
    - Task scheduler status
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Health Types ──


class HealthStatus(str, Enum):
    """Component health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Result of a single health check."""

    component: str
    status: HealthStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latency_seconds: float = 0.0


@dataclass
class HealthReport:
    """Aggregate health report for the AI Agent Platform."""

    overall_status: HealthStatus = HealthStatus.UNKNOWN
    checks: List[HealthCheck] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_healthy(self) -> bool:
        """Check if overall status is healthy."""
        return self.overall_status == HealthStatus.HEALTHY

    @property
    def is_degraded(self) -> bool:
        """Check if system is in degraded state."""
        return self.overall_status == HealthStatus.DEGRADED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.overall_status.value,
            "generated_at": self.generated_at.isoformat(),
            "checks": [
                {
                    "component": c.component,
                    "status": c.status.value,
                    "message": c.message,
                    "latency_seconds": c.latency_seconds,
                }
                for c in self.checks
            ],
        }


# ── Health Checker ──


class AgentHealthChecker:
    """Health monitoring for the AI Agent Platform.

    Performs component-level health checks and generates
    aggregate health reports for platform integration.

    Usage:
        checker = AgentHealthChecker()
        checker.register_check("runtime", lambda: check_runtime())
        report = checker.check_all()
    """

    def __init__(self) -> None:
        self._checks: Dict[str, Callable[[], HealthCheck]] = {}
        self._last_report: Optional[HealthReport] = None
        logger.info("AgentHealthChecker created")

    # ── Check Registration ──

    def register_check(
        self,
        component: str,
        check_fn: Callable[[], HealthCheck],
    ) -> None:
        """Register a health check function.

        Args:
            component: Component name.
            check_fn: Function returning a HealthCheck.
        """
        self._checks[component] = check_fn
        logger.debug(f"Registered health check: {component}")

    def unregister_check(self, component: str) -> None:
        """Remove a health check."""
        self._checks.pop(component, None)

    # ── Health Checks ──

    def check_all(self) -> HealthReport:
        """Run all registered health checks.

        Returns:
            Aggregate HealthReport.
        """
        checks: List[HealthCheck] = []
        unhealthy_count = 0
        degraded_count = 0

        for component, check_fn in self._checks.items():
            try:
                check = check_fn()
                checks.append(check)

                if check.status == HealthStatus.UNHEALTHY:
                    unhealthy_count += 1
                elif check.status == HealthStatus.DEGRADED:
                    degraded_count += 1

            except Exception as e:
                checks.append(HealthCheck(
                    component=component,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed with exception: {e}",
                ))
                unhealthy_count += 1

        # Determine overall status
        if unhealthy_count > 0:
            overall = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall = HealthStatus.DEGRADED
        elif not checks:
            overall = HealthStatus.UNKNOWN
        else:
            overall = HealthStatus.HEALTHY

        report = HealthReport(
            overall_status=overall,
            checks=checks,
        )
        self._last_report = report

        logger.info(f"Health check complete: {overall.value}")
        return report

    def check_component(self, component: str) -> Optional[HealthCheck]:
        """Run a specific component's health check.

        Args:
            component: Component name.

        Returns:
            HealthCheck or None if not registered.
        """
        check_fn = self._checks.get(component)
        if not check_fn:
            return None

        try:
            return check_fn()
        except Exception as e:
            return HealthCheck(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )

    # ── Static Check Helpers ──

    @staticmethod
    def check_runtime(runtime: Any) -> HealthCheck:
        """Check agent runtime health."""
        if hasattr(runtime, "is_healthy"):
            healthy = runtime.is_healthy()
        else:
            healthy = True
        return HealthCheck(
            component="agent_runtime",
            status=HealthStatus.HEALTHY if healthy else HealthStatus.DEGRADED,
            message="Runtime operational" if healthy else "Runtime degraded",
        )

    @staticmethod
    def check_session_manager(session_mgr: Any) -> HealthCheck:
        """Check session manager health."""
        summary = session_mgr.get_summary() if hasattr(session_mgr, "get_summary") else {}
        active = summary.get("active_sessions", 0)
        max_sessions = summary.get("max_sessions", 1000)

        if active > max_sessions * 0.9:
            return HealthCheck(
                component="session_manager",
                status=HealthStatus.DEGRADED,
                message=f"Session capacity near limit: {active}/{max_sessions}",
            )
        return HealthCheck(
            component="session_manager",
            status=HealthStatus.HEALTHY,
            message=f"Sessions: {active}/{max_sessions}",
        )

    @staticmethod
    def check_memory(memory_mgr: Any) -> HealthCheck:
        """Check memory subsystem health."""
        summary = memory_mgr.get_summary() if hasattr(memory_mgr, "get_summary") else {}
        total_size = memory_mgr.get_total_size() if hasattr(memory_mgr, "get_total_size") else 0
        return HealthCheck(
            component="memory",
            status=HealthStatus.HEALTHY,
            message=f"Memory entries: {total_size}",
            details=summary,
        )

    @staticmethod
    def check_engine(engine: Any) -> HealthCheck:
        """Check agent engine health."""
        try:
            status = engine.get_status()
            initialized = status.get("initialized", False)
            return HealthCheck(
                component="agent_engine",
                status=HealthStatus.HEALTHY if initialized else HealthStatus.DEGRADED,
                message=f"Engine {'initialized' if initialized else 'not initialized'}",
                details=status,
            )
        except Exception as e:
            return HealthCheck(
                component="agent_engine",
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )

    # ── Status ──

    def get_last_report(self) -> Optional[HealthReport]:
        """Get the last generated health report."""
        return self._last_report

    def get_summary(self) -> Dict[str, Any]:
        """Get health checker summary."""
        return {
            "registered_checks": list(self._checks.keys()),
            "last_report": self._last_report.to_dict() if self._last_report else None,
        }
