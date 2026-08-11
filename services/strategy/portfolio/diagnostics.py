"""
Portfolio Decision Diagnostics — Diagnostic analysis for portfolio decision subsystems.

Part of Commit 13 Part 1.3: Portfolio Decision.

Checks:
    - PortfolioDecisionEngine health
    - PositionSizingEngine health
    - CapitalAllocator health
    - ExposureManager health
    - DecisionRegistry consistency
    - Order netting efficiency
    - Intent builder pipeline health
    - Resource utilization
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class DiagnosticSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"
    OK = "OK"


@dataclass
class DiagnosticIssue:
    """A single diagnostic finding."""
    category: str
    severity: DiagnosticSeverity
    message: str
    detail: Optional[str] = None
    recommendation: Optional[str] = None


@dataclass
class DiagnosticReport:
    """Full diagnostic report for portfolio decision subsystems."""
    report_id: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    overall_status: DiagnosticSeverity = DiagnosticSeverity.OK
    issues: List[DiagnosticIssue] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == DiagnosticSeverity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == DiagnosticSeverity.WARNING)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "overall_status": self.overall_status.value,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "total_issues": len(self.issues),
            "issues": [
                {
                    "category": i.category,
                    "severity": i.severity.value,
                    "message": i.message,
                    "detail": i.detail,
                    "recommendation": i.recommendation,
                }
                for i in self.issues
            ],
            "metrics": self.metrics,
        }


# ---------------------------------------------------------------------------
# Portfolio Diagnostics
# ---------------------------------------------------------------------------

class PortfolioDiagnostics:
    """Diagnostic analyzer for portfolio decision subsystems.

    Provides comprehensive checks across the entire portfolio decision
    pipeline: sizing, allocation, exposure, conflict resolution, netting,
    and order intent generation.
    """

    def __init__(self):
        self._decision_engine: Optional[Any] = None
        self._sizing_engine: Optional[Any] = None
        self._capital_allocator: Optional[Any] = None
        self._exposure_manager: Optional[Any] = None
        self._leverage_controller: Optional[Any] = None
        self._conflict_resolver: Optional[Any] = None
        self._netting_engine: Optional[Any] = None
        self._intent_builder: Optional[Any] = None
        self._decision_registry: Optional[Any] = None
        self._recommendation_engine: Optional[Any] = None

        # Track instruments seen during netting check for duplicates
        self._netted_instruments: Set[str] = set()

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
        decision_registry: Optional[Any] = None,
        recommendation_engine: Optional[Any] = None,
    ) -> None:
        """Wire up references to all portfolio decision subsystems for inspection."""
        self._decision_engine = decision_engine
        self._sizing_engine = sizing_engine
        self._capital_allocator = capital_allocator
        self._exposure_manager = exposure_manager
        self._leverage_controller = leverage_controller
        self._conflict_resolver = conflict_resolver
        self._netting_engine = netting_engine
        self._intent_builder = intent_builder
        self._decision_registry = decision_registry
        self._recommendation_engine = recommendation_engine
        logger.info("PortfolioDiagnostics wired with %d subsystems",
                     sum(1 for x in [
                         self._decision_engine, self._sizing_engine,
                         self._capital_allocator, self._exposure_manager,
                         self._leverage_controller, self._conflict_resolver,
                         self._netting_engine, self._intent_builder,
                         self._decision_registry, self._recommendation_engine,
                     ] if x is not None))

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    async def run_full_diagnostics(self) -> DiagnosticReport:
        """Run all diagnostic checks across portfolio decision subsystems."""
        import uuid
        report = DiagnosticReport(report_id=f"pfdiag_{uuid.uuid4().hex[:8]}")

        checks = [
            self._check_decision_engine,
            self._check_sizing_engine,
            self._check_capital_allocator,
            self._check_exposure_manager,
            self._check_leverage_controller,
            self._check_conflict_resolver,
            self._check_netting_engine,
            self._check_intent_builder,
            self._check_decision_registry,
            self._check_recommendation_engine,
            self._check_resource_utilization,
            self._check_pipeline_integrity,
        ]

        for check in checks:
            issues = await check()
            report.issues.extend(issues)

        # Determine overall status
        if any(i.severity == DiagnosticSeverity.CRITICAL for i in report.issues):
            report.overall_status = DiagnosticSeverity.CRITICAL
        elif any(i.severity == DiagnosticSeverity.WARNING for i in report.issues):
            report.overall_status = DiagnosticSeverity.WARNING
        else:
            report.overall_status = DiagnosticSeverity.OK

        logger.info("Portfolio diagnostics complete: %s (critical=%d, warning=%d)",
                     report.overall_status.value, report.critical_count, report.warning_count)

        return report

    # ------------------------------------------------------------------
    # Check Methods
    # ------------------------------------------------------------------

    async def _check_decision_engine(self) -> List[DiagnosticIssue]:
        issues = []
        if not self._decision_engine:
            issues.append(DiagnosticIssue(
                category="portfolio_decision_engine",
                severity=DiagnosticSeverity.CRITICAL,
                message="PortfolioDecisionEngine not wired",
                recommendation="Wire the engine before running diagnostics",
            ))
            return issues

        if not self._decision_engine.is_initialized:
            issues.append(DiagnosticIssue(
                category="portfolio_decision_engine",
                severity=DiagnosticSeverity.CRITICAL,
                message="PortfolioDecisionEngine not initialized",
                recommendation="Call engine.initialize() before use",
            ))
        else:
            # Check internal metrics
            engine_metrics = self._decision_engine.get_metrics()
            report.metrics["engine_metrics"] = engine_metrics

            issues.append(DiagnosticIssue(
                category="portfolio_decision_engine",
                severity=DiagnosticSeverity.OK,
                message="PortfolioDecisionEngine initialized and healthy",
                detail=f"Evaluated: {engine_metrics.get('evaluated_total', 0)}, "
                       f"Decisions: {engine_metrics.get('decisions_total', 0)}",
            ))

        return issues

    async def _check_sizing_engine(self) -> List[DiagnosticIssue]:
        issues = []
        if not self._sizing_engine:
            issues.append(DiagnosticIssue(
                category="position_sizing",
                severity=DiagnosticSeverity.WARNING,
                message="PositionSizingEngine not wired — sizing diagnostics skipped",
            ))
            return issues

        if not getattr(self._sizing_engine, 'is_initialized', False):
            issues.append(DiagnosticIssue(
                category="position_sizing",
                severity=DiagnosticSeverity.CRITICAL,
                message="PositionSizingEngine not initialized",
            ))
            return issues

        issues.append(DiagnosticIssue(
            category="position_sizing",
            severity=DiagnosticSeverity.OK,
            message="PositionSizingEngine operational",
        ))

        # Check model availability
        registry = getattr(self._sizing_engine, 'registry', None)
        if registry:
            model_count = getattr(registry, 'model_count', 0)
            if model_count == 0:
                issues.append(DiagnosticIssue(
                    category="sizing_models",
                    severity=DiagnosticSeverity.WARNING,
                    message="No sizing models registered",
                    recommendation="Register at least one sizing model (Kelly, Fixed Fractional, etc.)",
                ))
            else:
                report.metrics["sizing_models_registered"] = model_count

        return issues

    async def _check_capital_allocator(self) -> List[DiagnosticIssue]:
        issues = []
        if not self._capital_allocator:
            issues.append(DiagnosticIssue(
                category="capital_allocator",
                severity=DiagnosticSeverity.WARNING,
                message="CapitalAllocator not wired — allocation diagnostics skipped",
            ))
            return issues

        if not getattr(self._capital_allocator, 'is_initialized', False):
            issues.append(DiagnosticIssue(
                category="capital_allocator",
                severity=DiagnosticSeverity.CRITICAL,
                message="CapitalAllocator not initialized",
            ))
            return issues

        issues.append(DiagnosticIssue(
            category="capital_allocator",
            severity=DiagnosticSeverity.OK,
            message="CapitalAllocator operational",
        ))

        # Check available capital pool
        pool = getattr(self._capital_allocator, 'capital_pool', None)
        if pool:
            available = getattr(pool, 'available', 0.0)
            total = getattr(pool, 'total', 0.0)
            report.metrics["capital_available"] = available
            report.metrics["capital_total"] = total
            if available <= 0:
                issues.append(DiagnosticIssue(
                    category="capital_pool",
                    severity=DiagnosticSeverity.WARNING,
                    message=f"No available capital (available={available}, total={total})",
                    recommendation="Refill capital pool or reduce allocations",
                ))

        return issues

    async def _check_exposure_manager(self) -> List[DiagnosticIssue]:
        issues = []
        if not self._exposure_manager:
            issues.append(DiagnosticIssue(
                category="exposure_manager",
                severity=DiagnosticSeverity.WARNING,
                message="ExposureManager not wired — exposure diagnostics skipped",
            ))
            return issues

        if not getattr(self._exposure_manager, 'is_initialized', False):
            issues.append(DiagnosticIssue(
                category="exposure_manager",
                severity=DiagnosticSeverity.CRITICAL,
                message="ExposureManager not initialized",
            ))
            return issues

        issues.append(DiagnosticIssue(
            category="exposure_manager",
            severity=DiagnosticSeverity.OK,
            message="ExposureManager operational",
        ))

        # Check exposure limit violations
        recent_breaches = getattr(self._exposure_manager, 'recent_limit_breaches', [])
        if recent_breaches:
            issues.append(DiagnosticIssue(
                category="exposure_limits",
                severity=DiagnosticSeverity.WARNING,
                message=f"{len(recent_breaches)} recent exposure limit breach(es)",
                recommendation="Review exposure limits or reduce position sizes",
            ))

        return issues

    async def _check_leverage_controller(self) -> List[DiagnosticIssue]:
        issues = []
        if not self._leverage_controller:
            return issues  # Leverage controller is optional

        if not getattr(self._leverage_controller, 'is_initialized', False):
            issues.append(DiagnosticIssue(
                category="leverage_controller",
                severity=DiagnosticSeverity.WARNING,
                message="LeverageController not initialized",
            ))
            return issues

        current_leverage = getattr(self._leverage_controller, 'current_leverage', None)
        max_leverage = getattr(self._leverage_controller, 'max_leverage', None)

        if current_leverage is not None:
            report.metrics["current_leverage"] = current_leverage
        if max_leverage is not None:
            report.metrics["max_leverage"] = max_leverage

        issues.append(DiagnosticIssue(
            category="leverage_controller",
            severity=DiagnosticSeverity.OK,
            message="LeverageController operational",
        ))

        return issues

    async def _check_conflict_resolver(self) -> List[DiagnosticIssue]:
        issues = []
        if not self._conflict_resolver:
            return issues

        if not getattr(self._conflict_resolver, 'is_initialized', False):
            issues.append(DiagnosticIssue(
                category="conflict_resolver",
                severity=DiagnosticSeverity.WARNING,
                message="StrategyConflictResolver not initialized",
            ))
            return issues

        conflict_count = getattr(self._conflict_resolver, 'last_conflict_count', None)
        if conflict_count is not None:
            report.metrics["recent_conflicts"] = conflict_count
            if conflict_count > 10:
                issues.append(DiagnosticIssue(
                    category="strategy_conflicts",
                    severity=DiagnosticSeverity.WARNING,
                    message=f"High conflict count: {conflict_count}",
                    recommendation="Review strategy priorities to reduce conflict frequency",
                ))

        issues.append(DiagnosticIssue(
            category="conflict_resolver",
            severity=DiagnosticSeverity.OK,
            message="StrategyConflictResolver operational",
        ))

        return issues

    async def _check_netting_engine(self) -> List[DiagnosticIssue]:
        issues = []
        if not self._netting_engine:
            return issues

        if not getattr(self._netting_engine, 'is_initialized', False):
            issues.append(DiagnosticIssue(
                category="order_netting",
                severity=DiagnosticSeverity.WARNING,
                message="OrderNettingEngine not initialized",
            ))
            return issues

        netting_stats = getattr(self._netting_engine, 'stats', None)
        if netting_stats:
            total_netted = getattr(netting_stats, 'total_netted', 0)
            report.metrics["total_netted_orders"] = total_netted

        issues.append(DiagnosticIssue(
            category="order_netting",
            severity=DiagnosticSeverity.OK,
            message="OrderNettingEngine operational",
        ))

        return issues

    async def _check_intent_builder(self) -> List[DiagnosticIssue]:
        issues = []
        if not self._intent_builder:
            issues.append(DiagnosticIssue(
                category="order_intent_builder",
                severity=DiagnosticSeverity.WARNING,
                message="OrderIntentBuilder not wired — intent diagnostics skipped",
            ))
            return issues

        if not getattr(self._intent_builder, 'is_initialized', False):
            issues.append(DiagnosticIssue(
                category="order_intent_builder",
                severity=DiagnosticSeverity.CRITICAL,
                message="OrderIntentBuilder not initialized",
            ))
            return issues

        issues.append(DiagnosticIssue(
            category="order_intent_builder",
            severity=DiagnosticSeverity.OK,
            message="OrderIntentBuilder operational",
        ))

        return issues

    async def _check_decision_registry(self) -> List[DiagnosticIssue]:
        issues = []
        if not self._decision_registry:
            return issues

        registered_types = getattr(self._decision_registry, 'type_count', None)
        registered_sources = getattr(self._decision_registry, 'source_count', None)

        if registered_types is not None:
            report.metrics["registered_decision_types"] = registered_types
            if registered_types == 0:
                issues.append(DiagnosticIssue(
                    category="decision_registry",
                    severity=DiagnosticSeverity.WARNING,
                    message="No decision types registered",
                    recommendation="Register decision types for proper tracking",
                ))

        issues.append(DiagnosticIssue(
            category="decision_registry",
            severity=DiagnosticSeverity.OK,
            message=f"DecisionRegistry: {registered_types or '?'} types, "
                     f"{registered_sources or '?'} sources",
        ))

        return issues

    async def _check_recommendation_engine(self) -> List[DiagnosticIssue]:
        issues = []
        if not self._recommendation_engine:
            return issues  # Recommendation engine is optional

        if not getattr(self._recommendation_engine, 'is_initialized', False):
            issues.append(DiagnosticIssue(
                category="recommendation_engine",
                severity=DiagnosticSeverity.WARNING,
                message="RecommendationEngine not initialized",
            ))
            return issues

        issues.append(DiagnosticIssue(
            category="recommendation_engine",
            severity=DiagnosticSeverity.OK,
            message="RecommendationEngine operational",
        ))

        return issues

    async def _check_resource_utilization(self) -> List[DiagnosticIssue]:
        """Check resource utilization for decision pipeline components."""
        issues = []
        # Track decision throughput and memory usage
        engine_metrics = {}
        if self._decision_engine and self._decision_engine.is_initialized:
            engine_metrics = self._decision_engine.get_metrics()

        total_processed = engine_metrics.get('evaluated_total', 0)
        report.metrics["signals_processed"] = total_processed

        return issues

    async def _check_pipeline_integrity(self) -> List[DiagnosticIssue]:
        """Verify the integrity of the decision pipeline end-to-end."""
        issues = []
        missing_components = []

        if not self._sizing_engine:
            missing_components.append("PositionSizingEngine")
        if not self._capital_allocator:
            missing_components.append("CapitalAllocator")
        if not self._exposure_manager:
            missing_components.append("ExposureManager")
        if not self._conflict_resolver:
            missing_components.append("StrategyConflictResolver")
        if not self._netting_engine:
            missing_components.append("OrderNettingEngine")
        if not self._intent_builder:
            missing_components.append("OrderIntentBuilder")

        if missing_components:
            issues.append(DiagnosticIssue(
                category="pipeline_integrity",
                severity=DiagnosticSeverity.WARNING,
                message=f"Incomplete decision pipeline: missing {', '.join(missing_components)}",
                recommendation="Wire all required components for full pipeline operation",
                detail=f"Pipeline: Sizing → Allocation → Exposure → Conflicts → Netting → Intent. "
                       f"Missing: {len(missing_components)} component(s)",
            ))
        else:
            issues.append(DiagnosticIssue(
                category="pipeline_integrity",
                severity=DiagnosticSeverity.OK,
                message="Full decision pipeline: Sizing → Allocation → Exposure → "
                        "Conflicts → Netting → Intent — ALL PRESENT",
            ))

        return issues

    # ------------------------------------------------------------------
    # Targeted Checks
    # ------------------------------------------------------------------

    async def check_sizing_health(self) -> List[DiagnosticIssue]:
        """Run sizing-specific diagnostics only."""
        return await self._check_sizing_engine()

    async def check_allocation_health(self) -> List[DiagnosticIssue]:
        """Run allocation-specific diagnostics only."""
        return await self._check_capital_allocator()

    async def check_exposure_health(self) -> List[DiagnosticIssue]:
        """Run exposure-specific diagnostics only."""
        return await self._check_exposure_manager()

    async def check_pipeline_integrity(self) -> List[DiagnosticIssue]:
        """Run pipeline integrity check only."""
        return await self._check_pipeline_integrity()
