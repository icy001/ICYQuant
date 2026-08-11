"""Autonomy Health Checker — system-level health assessment for the autonomous research subsystem.

Checks all autonomy components:
    - AutonomyRuntime      — runtime health
    - GoalManager           — goal tracking health
    - MarketMonitor         — monitoring health
    - SignalDiscovery       — signal pipeline health
    - FactorMining          — factor discovery health
    - AutonomousBacktest    — backtest engine health
    - RiskReview            — risk assessment health
    - ComplianceChecker     — compliance engine health
    - ApprovalGateway       — HITL gateway health
    - ConfidenceEngine      — confidence scoring health
    - SafetyController      — safety gate health
    - LearningPipeline      — learning pipeline health
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    latency_ms: float = 0.0


@dataclass
class HealthReport:
    overall: HealthStatus = HealthStatus.UNKNOWN
    components: List[ComponentHealth] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    @property
    def is_ok(self) -> bool:
        return self.overall == HealthStatus.OK

    def as_dict(self) -> Dict[str, Any]:
        return {
            "overall": self.overall.value,
            "is_ok": self.is_ok,
            "generated_at": self.generated_at,
            "components": [
                {"name": c.name, "status": c.status.value, "message": c.message, "latency_ms": round(c.latency_ms, 2)}
                for c in self.components
            ],
        }


class AutonomyHealthChecker:
    """System-level health checker for the autonomous research subsystem.

    Usage:
        checker = AutonomyHealthChecker()
        await checker.initialize()
        checker.register_check("market_monitor", my_check_fn)
        report = await checker.check_all()
    """

    def __init__(self) -> None:
        self._checks: Dict[str, Any] = {}
        self._history: List[HealthReport] = []
        self._max_history: int = 200
        self._initialized: bool = False
        logger.info("AutonomyHealthChecker created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("AutonomyHealthChecker initialized")

    async def shutdown(self) -> None:
        self._checks.clear()
        self._history.clear()
        self._initialized = False
        logger.info("AutonomyHealthChecker shutdown complete")

    def register_check(self, component_name: str, check_fn: Any) -> None:
        self._checks[component_name] = check_fn

    async def check_all(self) -> HealthReport:
        components: List[ComponentHealth] = []
        for name, check_fn in self._checks.items():
            try:
                start = time.monotonic()
                result = await check_fn()
                elapsed = (time.monotonic() - start) * 1000
                if isinstance(result, ComponentHealth):
                    result.latency_ms = round(elapsed, 2)
                    components.append(result)
                elif isinstance(result, dict):
                    components.append(ComponentHealth(
                        name=name,
                        status=HealthStatus(result.get("status", "unknown")),
                        message=result.get("message", ""),
                        latency_ms=round(elapsed, 2),
                    ))
            except Exception as e:
                logger.error("Health check failed for %s: %s", name, e)
                components.append(ComponentHealth(name=name, status=HealthStatus.DOWN, message=str(e)))

        statuses = [c.status for c in components]
        if HealthStatus.DOWN in statuses:
            overall = HealthStatus.DOWN
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        elif not components:
            overall = HealthStatus.UNKNOWN
        else:
            overall = HealthStatus.OK

        report = HealthReport(overall=overall, components=components)
        self._history.append(report)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        return report

    def get_latest(self) -> Optional[HealthReport]:
        return self._history[-1] if self._history else None

    def get_summary(self) -> Dict[str, Any]:
        latest = self.get_latest()
        return {
            "initialized": self._initialized,
            "registered_checks": sorted(self._checks.keys()),
            "latest_overall": latest.overall.value if latest else "unknown",
        }

    @property
    def registered_components(self) -> List[str]:
        return sorted(self._checks.keys())
