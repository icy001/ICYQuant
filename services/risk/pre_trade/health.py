"""
Pre-Trade Health — Health check probes for the Pre-Trade Risk Platform.

Provides liveness, readiness, and startup health checks for K8s
orchestration and internal monitoring.

Probes:
- Liveness: Is the process alive?
- Readiness: Is the pipeline ready to accept requests?
- Startup: Did the pipeline initialize successfully?
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Component health status."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    STARTING = "STARTING"


class ProbeType(str, Enum):
    """Health probe type."""
    LIVENESS = "LIVENESS"
    READINESS = "READINESS"
    STARTUP = "STARTUP"


@dataclass
class ComponentHealth:
    """Health status of a single pre-trade component."""
    component: str
    status: HealthStatus = HealthStatus.HEALTHY
    message: str = ""
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    consecutive_failures: int = 0
    max_consecutive_failures: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PreTradeHealthReport:
    """Aggregate health report for the pre-trade platform."""
    overall_status: HealthStatus = HealthStatus.HEALTHY
    probe_type: ProbeType = ProbeType.READINESS
    components: dict[str, ComponentHealth] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uptime_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.overall_status.value,
            "probe": self.probe_type.value,
            "components": {
                name: {
                    "status": h.status.value,
                    "message": h.message,
                    "consecutive_failures": h.consecutive_failures,
                }
                for name, h in self.components.items()
            },
            "generated_at": self.generated_at.isoformat(),
            "uptime_seconds": self.uptime_seconds,
        }


class PreTradeHealthChecker:
    """
    Health check system for the Pre-Trade Risk Platform.

    Provides liveness, readiness, and startup probes with circuit-breaker
    logic: components are marked UNHEALTHY after 3 consecutive failures.

    Usage::

        checker = PreTradeHealthChecker(engine=engine, runtime=runtime)
        liveness = await checker.liveness()
        readiness = await checker.readiness()
    """

    def __init__(
        self,
        engine: Optional[Any] = None,
        runtime: Optional[Any] = None,
        rule_chain: Optional[Any] = None,
        approval_workflow: Optional[Any] = None,
    ) -> None:
        self._engine = engine
        self._runtime = runtime
        self._rule_chain = rule_chain
        self._approval_workflow = approval_workflow
        self._startup_time: Optional[datetime] = None
        self._component_health: dict[str, ComponentHealth] = {}

    async def mark_startup(self) -> None:
        """Mark the platform as started."""
        self._startup_time = datetime.now(timezone.utc)

    async def liveness(self) -> PreTradeHealthReport:
        """
        Liveness probe — is the process alive?

        Returns HEALTHY as long as the process can respond.
        """
        components = {
            "process": ComponentHealth(
                component="process",
                status=HealthStatus.HEALTHY,
                message="Process is alive.",
            ),
        }
        return PreTradeHealthReport(
            overall_status=HealthStatus.HEALTHY,
            probe_type=ProbeType.LIVENESS,
            components=components,
            uptime_seconds=(
                (datetime.now(timezone.utc) - self._startup_time).total_seconds()
                if self._startup_time else 0.0
            ),
        )

    async def readiness(self) -> PreTradeHealthReport:
        """
        Readiness probe — is the pipeline ready to accept requests?

        Checks all critical components: engine, runtime, rule chain,
        and approval workflow.
        """
        checks = await asyncio.gather(
            self._check_engine(),
            self._check_runtime(),
            self._check_rule_chain(),
            self._check_approval_workflow(),
        )

        components = {
            c.component: c for c in checks
        }

        statuses = [c.status for c in checks]
        if HealthStatus.UNHEALTHY in statuses:
            overall = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        return PreTradeHealthReport(
            overall_status=overall,
            probe_type=ProbeType.READINESS,
            components=components,
            uptime_seconds=(
                (datetime.now(timezone.utc) - self._startup_time).total_seconds()
                if self._startup_time else 0.0
            ),
        )

    async def startup(self) -> PreTradeHealthReport:
        """
        Startup probe — has the pipeline initialized successfully?

        Returns HEALTHY only if all components initialized without errors.
        """
        checks = await asyncio.gather(
            self._check_engine(),
            self._check_runtime(),
            self._check_rule_chain(),
            self._check_approval_workflow(),
        )

        components = {c.component: c for c in checks}

        all_healthy = all(c.status == HealthStatus.HEALTHY for c in checks)
        overall = HealthStatus.HEALTHY if all_healthy else HealthStatus.STARTING

        return PreTradeHealthReport(
            overall_status=overall,
            probe_type=ProbeType.STARTUP,
            components=components,
            uptime_seconds=0.0,
        )

    async def _check_engine(self) -> ComponentHealth:
        existing = self._component_health.get("pre_trade_engine")
        if not self._engine:
            return ComponentHealth(
                component="pre_trade_engine",
                status=HealthStatus.UNHEALTHY,
                message="Engine not connected.",
            )
        try:
            await self._engine.get_stats()
            return ComponentHealth(
                component="pre_trade_engine",
                status=HealthStatus.HEALTHY,
                message="Engine is responsive.",
                consecutive_failures=0,
            )
        except Exception as e:
            failures = (existing.consecutive_failures + 1) if existing else 1
            status = (
                HealthStatus.UNHEALTHY
                if failures >= 3
                else HealthStatus.DEGRADED
            )
            health = ComponentHealth(
                component="pre_trade_engine",
                status=status,
                message=f"Engine unresponsive: {e}",
                consecutive_failures=failures,
            )
            self._component_health["pre_trade_engine"] = health
            return health

    async def _check_runtime(self) -> ComponentHealth:
        existing = self._component_health.get("pre_trade_runtime")
        if not self._runtime:
            return ComponentHealth(
                component="pre_trade_runtime",
                status=HealthStatus.UNHEALTHY,
                message="Runtime not connected.",
            )
        try:
            await self._runtime.health_check()
            return ComponentHealth(
                component="pre_trade_runtime",
                status=HealthStatus.HEALTHY,
                message="Runtime is responsive.",
                consecutive_failures=0,
            )
        except Exception as e:
            failures = (existing.consecutive_failures + 1) if existing else 1
            status = (
                HealthStatus.UNHEALTHY
                if failures >= 3
                else HealthStatus.DEGRADED
            )
            health = ComponentHealth(
                component="pre_trade_runtime",
                status=status,
                message=f"Runtime unresponsive: {e}",
                consecutive_failures=failures,
            )
            self._component_health["pre_trade_runtime"] = health
            return health

    async def _check_rule_chain(self) -> ComponentHealth:
        existing = self._component_health.get("rule_chain")
        if not self._rule_chain:
            return ComponentHealth(
                component="rule_chain",
                status=HealthStatus.UNHEALTHY,
                message="Rule chain not connected.",
            )
        try:
            stats = self._rule_chain.get_stats()
            enabled = stats.get("enabled_count", 0)
            return ComponentHealth(
                component="rule_chain",
                status=HealthStatus.HEALTHY if enabled > 0 else HealthStatus.DEGRADED,
                message=f"{enabled} checkers enabled.",
                consecutive_failures=0,
            )
        except Exception as e:
            failures = (existing.consecutive_failures + 1) if existing else 1
            health = ComponentHealth(
                component="rule_chain",
                status=HealthStatus.UNHEALTHY,
                message=f"Rule chain failed: {e}",
                consecutive_failures=failures,
            )
            self._component_health["rule_chain"] = health
            return health

    async def _check_approval_workflow(self) -> ComponentHealth:
        existing = self._component_health.get("approval_workflow")
        if not self._approval_workflow:
            return ComponentHealth(
                component="approval_workflow",
                status=HealthStatus.HEALTHY,
                message="Approval workflow not connected (non-critical).",
            )
        try:
            await self._approval_workflow.get_pending()
            return ComponentHealth(
                component="approval_workflow",
                status=HealthStatus.HEALTHY,
                message="Approval workflow is responsive.",
                consecutive_failures=0,
            )
        except Exception as e:
            failures = (existing.consecutive_failures + 1) if existing else 1
            health = ComponentHealth(
                component="approval_workflow",
                status=HealthStatus.DEGRADED,
                message=f"Approval workflow degraded: {e}",
                consecutive_failures=failures,
            )
            self._component_health["approval_workflow"] = health
            return health
