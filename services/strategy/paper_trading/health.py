"""
Paper Trading Health Check
==========================
Liveness and readiness checks for paper trading subsystems.

Components monitored:
    - PaperTradingEngine
    - VirtualExchange
    - VirtualOMS
    - VirtualPortfolio
    - VirtualAccount
    - ExecutionSimulator
    - KillSwitch
    - PerformanceEvaluator
    - PromotionWorkflow
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class PTComponentStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class PTHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


@dataclass
class PTComponentHealth:
    component: str
    status: PTComponentStatus = PTComponentStatus.UNKNOWN
    message: str = ""
    latency_ms: float = 0.0
    last_checked: Optional[datetime] = None
    last_error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": round(self.latency_ms, 3),
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "last_error": self.last_error,
            "details": self.details,
        }


@dataclass
class PTHealthReport:
    overall_status: PTHealthStatus = PTHealthStatus.HEALTHY
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    components: List[PTComponentHealth] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def healthy_count(self) -> int:
        return sum(1 for c in self.components if c.status == PTComponentStatus.HEALTHY)

    @property
    def degraded_count(self) -> int:
        return sum(1 for c in self.components if c.status == PTComponentStatus.DEGRADED)

    @property
    def unhealthy_count(self) -> int:
        return sum(1 for c in self.components if c.status == PTComponentStatus.UNHEALTHY)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status.value,
            "checked_at": self.checked_at.isoformat(),
            "healthy_count": self.healthy_count,
            "degraded_count": self.degraded_count,
            "unhealthy_count": self.unhealthy_count,
            "components": [c.to_dict() for c in self.components],
            "metadata": self.metadata,
        }


class PaperTradingHealthChecker:
    """Health checker for the paper trading platform."""

    def __init__(self):
        self._engine: Optional[Any] = None
        self._virtual_exchange: Optional[Any] = None
        self._virtual_oms: Optional[Any] = None
        self._virtual_portfolio: Optional[Any] = None
        self._virtual_account: Optional[Any] = None
        self._execution_simulator: Optional[Any] = None
        self._kill_switch: Optional[Any] = None
        self._performance_evaluator: Optional[Any] = None
        self._promotion_workflow: Optional[Any] = None

        self._last_report: Optional[PTHealthReport] = None
        self._consecutive_unhealthy: int = 0
        self._circuit_open: bool = False
        self._degraded_latency_ms: float = 500.0
        self._unhealthy_latency_ms: float = 2000.0

    def wire(self, **kwargs: Any) -> None:
        for name, component in kwargs.items():
            if hasattr(self, f"_{name}"):
                setattr(self, f"_{name}", component)
        logger.info("PaperTradingHealthChecker wired")

    async def check_health(self) -> PTHealthReport:
        report = PTHealthReport()

        checks: List[Callable[[], Any]] = [
            lambda: self._check("PaperTradingEngine", self._engine, True),
            lambda: self._check("VirtualExchange", self._virtual_exchange, True),
            lambda: self._check("VirtualOMS", self._virtual_oms, True),
            lambda: self._check("VirtualPortfolio", self._virtual_portfolio, True),
            lambda: self._check("VirtualAccount", self._virtual_account, False),
            lambda: self._check("ExecutionSimulator", self._execution_simulator, True),
            lambda: self._check("KillSwitch", self._kill_switch, False),
            lambda: self._check("PerformanceEvaluator", self._performance_evaluator, False),
            lambda: self._check("PromotionWorkflow", self._promotion_workflow, False),
        ]

        results = await asyncio.gather(*[asyncio.to_thread(c) for c in checks])
        report.components = list(results)

        if any(c.status == PTComponentStatus.UNHEALTHY for c in report.components):
            report.overall_status = PTHealthStatus.UNHEALTHY
            self._consecutive_unhealthy += 1
        elif any(c.status == PTComponentStatus.DEGRADED for c in report.components):
            report.overall_status = PTHealthStatus.DEGRADED
            self._consecutive_unhealthy = 0
        else:
            report.overall_status = PTHealthStatus.HEALTHY
            self._consecutive_unhealthy = 0

        if self._consecutive_unhealthy >= 3 and not self._circuit_open:
            self._circuit_open = True
            logger.critical("PAPER TRADING CIRCUIT OPENED after %d consecutive unhealthy",
                            self._consecutive_unhealthy)

        self._last_report = report
        return report

    def _check(self, name: str, component: Optional[Any],
               is_critical: bool) -> PTComponentHealth:
        start = datetime.now(timezone.utc)
        health = PTComponentHealth(component=name, last_checked=start)

        if component is None:
            if is_critical:
                health.status = PTComponentStatus.UNHEALTHY
                health.message = f"{name} is not wired (CRITICAL)"
            else:
                health.status = PTComponentStatus.HEALTHY
                health.message = f"{name} not wired (optional)"
            return health

        try:
            if not getattr(component, 'is_initialized', False):
                health.status = PTComponentStatus.UNHEALTHY
                health.message = f"{name} not initialized"
                return health

            health.status = PTComponentStatus.HEALTHY
            health.message = f"{name} healthy"
            health.details = getattr(component, 'get_metrics', lambda: {})()
        except Exception as exc:
            health.status = PTComponentStatus.UNHEALTHY
            health.message = f"{name} check failed: {exc}"
            health.last_error = str(exc)
        finally:
            health.latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        return health

    async def check_liveness(self) -> PTHealthReport:
        report = PTHealthReport()
        report.metadata["probe"] = "liveness"
        for name, comp in [
            ("PaperTradingEngine", self._engine),
            ("VirtualExchange", self._virtual_exchange),
            ("VirtualOMS", self._virtual_oms),
            ("ExecutionSimulator", self._execution_simulator),
        ]:
            report.components.append(self._check(name, comp, True))

        if any(c.status == PTComponentStatus.UNHEALTHY for c in report.components):
            report.overall_status = PTHealthStatus.UNHEALTHY
        return report

    async def check_readiness(self) -> PTHealthReport:
        full = await self.check_health()
        full.metadata["probe"] = "readiness"
        if full.unhealthy_count > 0:
            full.overall_status = PTHealthStatus.UNHEALTHY
        elif full.degraded_count > 0:
            full.overall_status = PTHealthStatus.DEGRADED
        return full

    def last_report(self) -> Optional[PTHealthReport]:
        return self._last_report

    def is_healthy(self) -> bool:
        if self._circuit_open:
            return False
        if not self._last_report:
            return False
        return self._last_report.overall_status == PTHealthStatus.HEALTHY

    def reset_circuit(self) -> None:
        self._circuit_open = False
        self._consecutive_unhealthy = 0

    def unhealthy_components(self) -> List[str]:
        if not self._last_report:
            return []
        return [c.component for c in self._last_report.components
                if c.status == PTComponentStatus.UNHEALTHY]
