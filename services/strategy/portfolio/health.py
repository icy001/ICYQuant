"""
Portfolio Decision Health Check — Liveness and readiness checks for portfolio
decision subsystems.

Part of Commit 13 Part 1.3: Portfolio Decision.

Components monitored:
    - PortfolioDecisionEngine (master orchestrator)
    - PositionSizingEngine (sizing subsystem)
    - CapitalAllocator (allocation subsystem)
    - ExposureManager (risk limits)
    - LeverageController (leverage policy)
    - StrategyConflictResolver (conflict detection)
    - OrderNettingEngine (netting subsystem)
    - OrderIntentBuilder (intent generation)
    - DecisionRegistry (metadata)
    - RecommendationEngine (AI recommendations)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ComponentStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class HealthStatus(str, Enum):
    """Overall health status (rolls up from component statuses)."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class ComponentHealth:
    """Health check result for a single component."""
    component: str
    status: ComponentStatus = ComponentStatus.UNKNOWN
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
class HealthReport:
    """Aggregated health report for all portfolio decision components."""
    overall_status: HealthStatus = HealthStatus.HEALTHY
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    components: List[ComponentHealth] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def healthy_count(self) -> int:
        return sum(1 for c in self.components if c.status == ComponentStatus.HEALTHY)

    @property
    def degraded_count(self) -> int:
        return sum(1 for c in self.components if c.status == ComponentStatus.DEGRADED)

    @property
    def unhealthy_count(self) -> int:
        return sum(1 for c in self.components if c.status == ComponentStatus.UNHEALTHY)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status.value,
            "checked_at": self.checked_at.isoformat(),
            "healthy_count": self.healthy_count,
            "degraded_count": self.degraded_count,
            "unhealthy_count": self.unhealthy_count,
            "total_components": len(self.components),
            "components": [c.to_dict() for c in self.components],
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Portfolio Decision Health Checker
# ---------------------------------------------------------------------------

class PortfolioDecisionHealthChecker:
    """Health checker for the portfolio decision platform.

    Runs liveness and readiness probes across all subsystems in the
    decision pipeline, producing a unified HealthReport.
    """

    def __init__(self):
        # Component references
        self._decision_engine: Optional[Any] = None
        self._sizing_engine: Optional[Any] = None
        self._capital_allocator: Optional[Any] = None
        self._exposure_manager: Optional[Any] = None
        self._leverage_controller: Optional[Any] = None
        self._conflict_resolver: Optional[Any] = None
        self._netting_engine: Optional[Any] = None
        self._intent_builder: Optional[Any] = None
        self._intent_validator: Optional[Any] = None
        self._intent_router: Optional[Any] = None
        self._decision_registry: Optional[Any] = None
        self._recommendation_engine: Optional[Any] = None

        # Health check history
        self._last_report: Optional[HealthReport] = None
        self._consecutive_unhealthy: int = 0
        self._circuit_open: bool = False

        # Config
        self._degraded_latency_threshold_ms: float = 500.0
        self._unhealthy_latency_threshold_ms: float = 2000.0

    def wire(
        self,
        decision_engine: Optional[Any] = None,
        sizing_engine: Optional[Any] = None,
        capital_allocator: Optional[Any] = None,
        exposure_manager: Optional[Any] = None,
        leverage_controller: Optional[Any] = None,
        conflict_resolver: Optional[Any] = None,
        netting_engine: Optional[Any] = None,
        intent_builder: Optional[Any] = None,
        intent_validator: Optional[Any] = None,
        intent_router: Optional[Any] = None,
        decision_registry: Optional[Any] = None,
        recommendation_engine: Optional[Any] = None,
    ) -> None:
        """Wire all portfolio decision subsystems for health checking."""
        self._decision_engine = decision_engine
        self._sizing_engine = sizing_engine
        self._capital_allocator = capital_allocator
        self._exposure_manager = exposure_manager
        self._leverage_controller = leverage_controller
        self._conflict_resolver = conflict_resolver
        self._netting_engine = netting_engine
        self._intent_builder = intent_builder
        self._intent_validator = intent_validator
        self._intent_router = intent_router
        self._decision_registry = decision_registry
        self._recommendation_engine = recommendation_engine
        logger.info("PortfolioDecisionHealthChecker wired")

    # ------------------------------------------------------------------
    # Full Health Check
    # ------------------------------------------------------------------

    async def check_health(self) -> HealthReport:
        """Run full health check across all wired components."""
        report = HealthReport()

        checks: List[Callable[[], Any]] = [
            lambda: self._check_component(
                "PortfolioDecisionEngine",
                self._decision_engine,
                is_critical=True,
            ),
            lambda: self._check_component(
                "PositionSizingEngine",
                self._sizing_engine,
                is_critical=True,
            ),
            lambda: self._check_component(
                "CapitalAllocator",
                self._capital_allocator,
                is_critical=True,
            ),
            lambda: self._check_component(
                "ExposureManager",
                self._exposure_manager,
                is_critical=False,
            ),
            lambda: self._check_component(
                "LeverageController",
                self._leverage_controller,
                is_critical=False,
            ),
            lambda: self._check_component(
                "StrategyConflictResolver",
                self._conflict_resolver,
                is_critical=False,
            ),
            lambda: self._check_component(
                "OrderNettingEngine",
                self._netting_engine,
                is_critical=False,
            ),
            lambda: self._check_component(
                "OrderIntentBuilder",
                self._intent_builder,
                is_critical=True,
            ),
            lambda: self._check_component(
                "OrderIntentValidator",
                self._intent_validator,
                is_critical=False,
            ),
            lambda: self._check_component(
                "OrderIntentRouter",
                self._intent_router,
                is_critical=False,
            ),
            lambda: self._check_component(
                "DecisionRegistry",
                self._decision_registry,
                is_critical=False,
            ),
            lambda: self._check_component(
                "RecommendationEngine",
                self._recommendation_engine,
                is_critical=False,
            ),
        ]

        # Run checks concurrently
        if asyncio.iscoroutinefunction(self._check_component):
            tasks = [asyncio.create_task(check_fn()) for check_fn in checks]  # type: ignore[arg-type]
            results = await asyncio.gather(*tasks)
            report.components = list(results)
        else:
            results = await asyncio.gather(
                *[asyncio.to_thread(check_fn) for check_fn in checks]
            )
            report.components = list(results)

        # Determine overall status
        if any(c.status == ComponentStatus.UNHEALTHY for c in report.components):
            report.overall_status = HealthStatus.UNHEALTHY
            self._consecutive_unhealthy += 1
        elif any(c.status == ComponentStatus.DEGRADED for c in report.components):
            report.overall_status = HealthStatus.DEGRADED
            self._consecutive_unhealthy = 0
        else:
            report.overall_status = HealthStatus.HEALTHY
            self._consecutive_unhealthy = 0

        # Circuit breaker: open after 3 consecutive unhealthy reports
        if self._consecutive_unhealthy >= 3 and not self._circuit_open:
            self._circuit_open = True
            logger.critical("HEALTH CIRCUIT OPENED after %d consecutive unhealthy",
                            self._consecutive_unhealthy)

        self._last_report = report
        logger.info("Health check complete: %s (unhealthy=%d, degraded=%d, healthy=%d)",
                     report.overall_status.value,
                     report.unhealthy_count, report.degraded_count, report.healthy_count)

        return report

    # ------------------------------------------------------------------
    # Single Component Check
    # ------------------------------------------------------------------

    async def _check_component(
        self,
        name: str,
        component: Optional[Any],
        is_critical: bool = False,
    ) -> ComponentHealth:
        """Check health of a single component."""
        start = datetime.now(timezone.utc)
        health = ComponentHealth(component=name, last_checked=start)

        if component is None:
            if is_critical:
                health.status = ComponentStatus.UNHEALTHY
                health.message = f"{name} is not wired (CRITICAL component missing)"
            else:
                health.status = ComponentStatus.HEALTHY
                health.message = f"{name} not wired (optional component)"
            return health

        try:
            # Check initialization status
            if not getattr(component, 'is_initialized', False):
                health.status = ComponentStatus.UNHEALTHY
                health.message = f"{name} not initialized"
                return health

            # Check component-specific metrics
            metrics = getattr(component, 'get_metrics', lambda: {})()
            health.details = metrics or {}

            # Check error count if available
            error_count = metrics.get('error_count', 0)
            if error_count > 10:
                health.status = ComponentStatus.DEGRADED
                health.message = f"{name} has {error_count} errors"
            else:
                health.status = ComponentStatus.HEALTHY
                health.message = f"{name} healthy"

        except Exception as exc:
            health.status = ComponentStatus.UNHEALTHY
            health.message = f"{name} check failed: {exc}"
            health.last_error = str(exc)
            logger.error("Health check failed for %s: %s", name, exc, exc_info=True)

        finally:
            health.latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        # Latency-based degradation
        if health.status == ComponentStatus.HEALTHY:
            if health.latency_ms > self._unhealthy_latency_threshold_ms:
                health.status = ComponentStatus.UNHEALTHY
                health.message = f"{name} latency critical ({health.latency_ms:.0f} ms)"
            elif health.latency_ms > self._degraded_latency_threshold_ms:
                health.status = ComponentStatus.DEGRADED
                health.message = f"{name} latency degraded ({health.latency_ms:.0f} ms)"

        return health

    # ------------------------------------------------------------------
    # Targeted Checks
    # ------------------------------------------------------------------

    async def check_liveness(self) -> HealthReport:
        """Liveness probe — check if core components are alive."""
        report = HealthReport()
        report.metadata["probe"] = "liveness"

        critical_components = [
            ("PortfolioDecisionEngine", self._decision_engine, True),
            ("PositionSizingEngine", self._sizing_engine, True),
            ("CapitalAllocator", self._capital_allocator, True),
            ("OrderIntentBuilder", self._intent_builder, True),
        ]

        for name, comp, critical in critical_components:
            health = await self._check_component(name, comp, is_critical=critical)
            report.components.append(health)

        if any(c.status == ComponentStatus.UNHEALTHY for c in report.components):
            report.overall_status = HealthStatus.UNHEALTHY
        else:
            report.overall_status = HealthStatus.HEALTHY

        return report

    async def check_readiness(self) -> HealthReport:
        """Readiness probe — check if pipeline is ready to process decisions."""
        report = HealthReport()
        report.metadata["probe"] = "readiness"

        # Full pipeline check
        full_report = await self.check_health()

        # Readiness requires ALL critical components healthy
        # and NO components unhealthy
        if full_report.unhealthy_count > 0:
            report.overall_status = HealthStatus.UNHEALTHY
        elif full_report.degraded_count > 0:
            report.overall_status = HealthStatus.DEGRADED
        else:
            report.overall_status = HealthStatus.HEALTHY

        report.components = full_report.components
        return report

    async def check_circuit_breaker(self) -> Dict[str, Any]:
        """Check the state of the health circuit breaker."""
        return {
            "circuit_open": self._circuit_open,
            "consecutive_unhealthy": self._consecutive_unhealthy,
            "last_report_overall": (
                self._last_report.overall_status.value if self._last_report else None
            ),
            "last_checked_at": (
                self._last_report.checked_at.isoformat() if self._last_report else None
            ),
        }

    def reset_circuit(self) -> None:
        """Manually reset the circuit breaker."""
        was_open = self._circuit_open
        self._circuit_open = False
        self._consecutive_unhealthy = 0
        if was_open:
            logger.info("HEALTH CIRCUIT RESET manually")

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def last_report(self) -> Optional[HealthReport]:
        """Return the last health report."""
        return self._last_report

    def is_healthy(self) -> bool:
        """Quick check: is the platform currently healthy?"""
        if self._circuit_open:
            return False
        if not self._last_report:
            return False
        return self._last_report.overall_status == HealthStatus.HEALTHY

    def unhealthy_components(self) -> List[str]:
        """Return names of currently unhealthy components."""
        if not self._last_report:
            return []
        return [c.component for c in self._last_report.components
                if c.status == ComponentStatus.UNHEALTHY]

    def set_latency_thresholds(self, degraded_ms: float, unhealthy_ms: float) -> None:
        """Configure latency thresholds for health reporting."""
        self._degraded_latency_threshold_ms = degraded_ms
        self._unhealthy_latency_threshold_ms = unhealthy_ms
        logger.info("Latency thresholds updated: degraded=%s ms, unhealthy=%s ms",
                     degraded_ms, unhealthy_ms)
