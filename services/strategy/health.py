"""
Strategy Platform Health Checker — component-level health reporting.

Provides health checks for every component in the strategy platform,
enabling integration with service discovery and monitoring systems.

Components checked:
    - Engine (state, readiness)
    - Runtime (slots, concurrency)
    - Registry (consistency, active count)
    - Loader (source availability)
    - Validator (rule completeness)
    - Scheduler (trigger status)
    - Snapshot Manager (storage health)
    - Recovery (success rate)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status for a component."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a single component."""

    component: str
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    latency_ms: float = 0.0
    detail: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_healthy(self) -> bool:
        return self.status == HealthStatus.HEALTHY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": round(self.latency_ms, 2),
            "detail": self.detail,
            "checked_at": self.checked_at.isoformat(),
        }


@dataclass
class HealthReport:
    """Aggregate health report for the strategy platform."""

    report_id: str
    overall: HealthStatus = HealthStatus.UNKNOWN
    components: List[ComponentHealth] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def healthy_components(self) -> int:
        return sum(1 for c in self.components if c.status == HealthStatus.HEALTHY)

    @property
    def degraded_components(self) -> int:
        return sum(1 for c in self.components if c.status == HealthStatus.DEGRADED)

    @property
    def unhealthy_components(self) -> int:
        return sum(1 for c in self.components if c.status == HealthStatus.UNHEALTHY)

    @property
    def is_healthy(self) -> bool:
        return self.overall == HealthStatus.HEALTHY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "overall": self.overall.value,
            "generated_at": self.generated_at.isoformat(),
            "summary": {
                "total": len(self.components),
                "healthy": self.healthy_components,
                "degraded": self.degraded_components,
                "unhealthy": self.unhealthy_components,
            },
            "components": [c.to_dict() for c in self.components],
        }


class StrategyHealthChecker:
    """Component-level health checker for the Strategy Platform.

    Runs individual health checks for each subsystem and produces a
    health report suitable for service discovery and monitoring integration.

    Usage:
        checker = StrategyHealthChecker()
        report = await checker.check_all(engine)
        assert report.is_healthy
    """

    def __init__(self) -> None:
        self._history: List[HealthReport] = []
        self._max_history: int = 100
        logger.info("StrategyHealthChecker created")

    async def check_all(self, engine: Any) -> HealthReport:
        """Run health checks on all strategy platform components.

        Args:
            engine: An initialized StrategyEngine instance.

        Returns:
            Complete HealthReport with all component statuses.
        """
        import uuid

        report = HealthReport(report_id=uuid.uuid4().hex[:12])

        # Run checks in parallel (logically)
        checks = [
            self._check_engine(engine),
            self._check_runtime(engine),
            self._check_registry(engine),
            self._check_loader(engine),
            self._check_validator(engine),
            self._check_scheduler(engine),
            self._check_snapshot_manager(engine),
            self._check_recovery(engine),
        ]

        for check_fn in checks:
            component = await check_fn
            report.components.append(component)

        report.overall = self._compute_overall(report.components)
        self._history.append(report)

        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        logger.info("Health check complete: %s (overall=%s, %d/%d healthy)",
                    report.report_id, report.overall.value,
                    report.healthy_components, len(report.components))
        return report

    # ── Individual Checks ──

    async def _check_engine(self, engine: Any) -> ComponentHealth:
        t0 = datetime.now(timezone.utc)
        try:
            state_ok = engine.is_ready
            state = engine.state.value
            if state_ok:
                return ComponentHealth(
                    component="engine",
                    status=HealthStatus.HEALTHY,
                    message=f"Engine ready (state={state})",
                    detail={"state": state},
                )
            else:
                return ComponentHealth(
                    component="engine",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Engine not ready (state={state})",
                    detail={"state": state},
                )
        except Exception as e:
            return ComponentHealth(
                component="engine",
                status=HealthStatus.UNHEALTHY,
                message=f"Engine check failed: {e}",
            )
        finally:
            latency = (datetime.now(timezone.utc) - t0).total_seconds() * 1000

    async def _check_runtime(self, engine: Any) -> ComponentHealth:
        try:
            summary = engine.runtime.get_summary()
            running = summary.get("running_count", 0)
            total = summary.get("total_slots", 0)
            max_slots = summary.get("quota_max", 50)

            if max_slots > 0 and total / max_slots > 0.9:
                return ComponentHealth(
                    component="runtime",
                    status=HealthStatus.DEGRADED,
                    message=f"High slot utilization ({total}/{max_slots})",
                    detail=summary,
                )

            return ComponentHealth(
                component="runtime",
                status=HealthStatus.HEALTHY,
                message=f"{running} running / {total} total slots",
                detail=summary,
            )
        except Exception as e:
            return ComponentHealth(
                component="runtime",
                status=HealthStatus.UNHEALTHY,
                message=f"Runtime check failed: {e}",
            )

    async def _check_registry(self, engine: Any) -> ComponentHealth:
        try:
            summary = engine.registry.get_summary()
            failed = len(engine.registry.list_by_state("failed"))
            if failed > 0:
                return ComponentHealth(
                    component="registry",
                    status=HealthStatus.DEGRADED,
                    message=f"{failed} strategies in FAILED state",
                    detail=summary,
                )
            return ComponentHealth(
                component="registry",
                status=HealthStatus.HEALTHY,
                message=f"Registry OK ({summary.get('total', 0)} total)",
                detail=summary,
            )
        except Exception as e:
            return ComponentHealth(
                component="registry",
                status=HealthStatus.UNHEALTHY,
                message=f"Registry check failed: {e}",
            )

    async def _check_loader(self, engine: Any) -> ComponentHealth:
        try:
            summary = engine.loader.get_summary()
            return ComponentHealth(
                component="loader",
                status=HealthStatus.HEALTHY,
                message="Loader operational",
                detail=summary,
            )
        except Exception as e:
            return ComponentHealth(
                component="loader",
                status=HealthStatus.UNHEALTHY,
                message=f"Loader check failed: {e}",
            )

    async def _check_validator(self, engine: Any) -> ComponentHealth:
        try:
            summary = engine.validator.get_summary()
            return ComponentHealth(
                component="validator",
                status=HealthStatus.HEALTHY,
                message="Validator operational",
                detail=summary,
            )
        except Exception as e:
            return ComponentHealth(
                component="validator",
                status=HealthStatus.UNHEALTHY,
                message=f"Validator check failed: {e}",
            )

    async def _check_scheduler(self, engine: Any) -> ComponentHealth:
        try:
            summary = engine.scheduler.get_summary()
            return ComponentHealth(
                component="scheduler",
                status=HealthStatus.HEALTHY,
                message="Scheduler operational",
                detail=summary,
            )
        except Exception as e:
            return ComponentHealth(
                component="scheduler",
                status=HealthStatus.UNHEALTHY,
                message=f"Scheduler check failed: {e}",
            )

    async def _check_snapshot_manager(self, engine: Any) -> ComponentHealth:
        try:
            summary = engine.snapshot_manager.get_summary()
            snap_count = summary.get("total_snapshots", 0)
            return ComponentHealth(
                component="snapshot_manager",
                status=HealthStatus.HEALTHY,
                message=f"{snap_count} snapshots",
                detail=summary,
            )
        except Exception as e:
            return ComponentHealth(
                component="snapshot_manager",
                status=HealthStatus.UNHEALTHY,
                message=f"Snapshot manager check failed: {e}",
            )

    async def _check_recovery(self, engine: Any) -> ComponentHealth:
        try:
            summary = engine.recovery.get_summary()
            success_rate = engine.recovery.get_success_rate()
            if success_rate < 0.5 and summary.get("total_recoveries", 0) > 0:
                return ComponentHealth(
                    component="recovery",
                    status=HealthStatus.DEGRADED,
                    message=f"Low recovery success rate: {success_rate:.0%}",
                    detail=summary,
                )
            return ComponentHealth(
                component="recovery",
                status=HealthStatus.HEALTHY,
                message=f"Recovery OK (rate={success_rate:.0%})",
                detail=summary,
            )
        except Exception as e:
            return ComponentHealth(
                component="recovery",
                status=HealthStatus.UNHEALTHY,
                message=f"Recovery check failed: {e}",
            )

    # ── Helpers ──

    def _compute_overall(self, components: List[ComponentHealth]) -> HealthStatus:
        """Determine overall health from component statuses."""
        statuses = {c.status for c in components}
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    # ── Query ──

    def get_latest_health(self) -> Optional[HealthReport]:
        return self._history[-1] if self._history else None

    def list_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._history[-limit:]]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "health_checks": len(self._history),
            "latest": self._history[-1].to_dict() if self._history else None,
        }
