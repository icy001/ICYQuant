"""AI Portfolio Intelligence Service — unified portfolio intelligence API.

Orchestrates all 8 portfolio intelligence engines:
  - AssetAllocationEngine: Strategic & tactical allocation
  - PositionSizingEngine: Risk-based position sizing
  - RiskBudgetEngine: Hierarchical risk budget management
  - ExposureEngine: Multi-dimensional exposure monitoring
  - PortfolioOptimizer: Multi-objective portfolio optimization
  - RebalanceEngine: Intelligent portfolio rebalancing
  - AttributionEngine: Performance attribution & decomposition
  - PortfolioMemory: Decision memory & analytics

Provides a single entry point for comprehensive portfolio analysis,
optimization, and monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from services.portfolio_intelligence.allocation import (
    AssetAllocation,
    AssetAllocationEngine,
    AssetClass,
    AllocationStrategy,
    AllocationResult,
    Horizon,
    RiskTolerance,
)
from services.portfolio_intelligence.sizing import (
    PositionSize,
    PositionSizingEngine,
    SizingMethod,
    SizingResult,
)
from services.portfolio_intelligence.budget import (
    BudgetAllocation,
    BudgetLevel,
    BudgetMethod,
    RiskBudget,
    RiskBudgetEngine,
)
from services.portfolio_intelligence.exposure import (
    Exposure,
    ExposureEngine,
    ExposureReport,
    ExposureType,
)
from services.portfolio_intelligence.optimizer import (
    Objective,
    OptimizationResult,
    PortfolioOptimizer,
)
from services.portfolio_intelligence.rebalance import (
    RebalanceEngine,
    RebalancePlan,
    RebalanceStrategy,
)
from services.portfolio_intelligence.attribution import (
    AttributionEngine,
    AttributionMethod,
    AttributionResult,
)
from services.portfolio_intelligence.memory import (
    MemoryEventType,
    PerformanceSnapshot,
    PortfolioMemory,
)

# ---------------------------------------------------------------------------
# Unified Result
# ---------------------------------------------------------------------------


@dataclass
class PortfolioBuildResult:
    """Complete portfolio build/analysis result.

    Attributes:
        allocation: Asset allocation result.
        sizing: Position sizing result.
        budget: Risk budget allocation.
        optimization: Portfolio optimization result.
        exposure: Exposure analysis report.
        rebalance: Rebalancing plan.
        attribution: Attribution result.
        summary: Aggregated summary dict.
        timestamp: Build time.
    """

    allocation: Optional[AllocationResult] = None
    sizing: Optional[SizingResult] = None
    budget: Optional[BudgetAllocation] = None
    optimization: Optional[OptimizationResult] = None
    exposure: Optional[ExposureReport] = None
    rebalance: Optional[RebalancePlan] = None
    attribution: Optional[AttributionResult] = None
    summary: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_healthy(self) -> bool:
        """Check overall portfolio health."""
        checks = []
        if self.allocation:
            checks.append(self.allocation.is_valid)
        if self.budget:
            checks.append(len(self.budget.exceeded_budgets) == 0)
        if self.exposure:
            checks.append(self.exposure.is_within_limits)
        if self.rebalance:
            checks.append(self.rebalance.status.value != "critical")
        return all(checks)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        d: dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "is_healthy": self.is_healthy,
        }
        if self.allocation:
            d["allocation"] = self.allocation.to_dict()
        if self.sizing:
            d["sizing"] = self.sizing.to_dict()
        if self.budget:
            d["budget"] = self.budget.to_dict()
        if self.optimization:
            d["optimization"] = self.optimization.to_dict()
        if self.exposure:
            d["exposure"] = self.exposure.to_dict()
        if self.rebalance:
            d["rebalance"] = self.rebalance.to_dict()
        if self.attribution:
            d["attribution"] = self.attribution.to_dict()
        if self.summary:
            d["summary"] = self.summary
        return d


# ---------------------------------------------------------------------------
# PortfolioIntelligenceService
# ---------------------------------------------------------------------------


class PortfolioIntelligenceService:
    """Unified AI portfolio intelligence service.

    Orchestrates the full portfolio management pipeline:
    allocation → sizing → optimization → budget → exposure → rebalancing → attribution.

    Attributes:
        allocator: Asset allocation engine.
        sizer: Position sizing engine.
        budget_engine: Risk budget engine.
        exposure_engine: Exposure control engine.
        optimizer: Portfolio optimization engine.
        rebalancer: Rebalancing engine.
        attributor: Performance attribution engine.
        memory: Portfolio decision memory.
    """

    def __init__(
        self,
        allocation_strategy: AllocationStrategy = AllocationStrategy.RISK_PARITY,
        sizing_method: SizingMethod = SizingMethod.FIXED_FRACTION,
        budget_method: BudgetMethod = BudgetMethod.EQUAL_DISTRIBUTION,
        optimization_objective: Objective = Objective.MAX_SHARPE,
    ) -> None:
        """Initialize the portfolio intelligence service.

        Args:
            allocation_strategy: Default asset allocation strategy.
            sizing_method: Default position sizing method.
            budget_method: Default risk budget method.
            optimization_objective: Default optimization objective.
        """
        self.allocator = AssetAllocationEngine(strategy=allocation_strategy)
        self.sizer = PositionSizingEngine(method=sizing_method)
        self.budget_engine = RiskBudgetEngine(method=budget_method)
        self.exposure_engine = ExposureEngine()
        self.optimizer = PortfolioOptimizer(objective=optimization_objective)
        self.rebalancer = RebalanceEngine()
        self.attributor = AttributionEngine()
        self.memory = PortfolioMemory()

    # ------------------------------------------------------------------
    # Comprehensive Build
    # ------------------------------------------------------------------

    def build(
        self,
        asset_data: Optional[dict[AssetClass, dict[str, Any]]] = None,
        position_data: Optional[list[dict[str, Any]]] = None,
        benchmark_data: Optional[dict[str, Any]] = None,
        current_weights: Optional[dict[str, float]] = None,
        target_weights: Optional[dict[str, float]] = None,
        constraints: Optional[dict[str, Any]] = None,
        nav: float = 1_000_000.0,
    ) -> PortfolioBuildResult:
        """Execute the full portfolio intelligence pipeline.

        Args:
            asset_data: Per-asset-class statistics (vol, return, corr).
            position_data: Individual position data for sizing and exposure.
            benchmark_data: Benchmark weights/returns for attribution.
            current_weights: Current portfolio weights.
            target_weights: Target portfolio weights (overrides allocation result).
            constraints: Global constraints (limits, bounds, etc.).
            nav: Net asset value.

        Returns:
            PortfolioBuildResult with results from all engines.
        """
        asset_data = asset_data or {}
        constraints = constraints or {}
        nav = max(nav, 1.0)

        # Step 1: Asset Allocation
        allocation = self.allocator.allocate(asset_data=asset_data)

        # Step 2: Position Sizing
        sizing = None
        if position_data:
            sizing = self.sizer.calculate(
                assets=position_data,
                portfolio_value=nav,
            )

        # Step 3: Portfolio Optimization
        if position_data:
            optimization = self.optimizer.optimize(
                assets=position_data,
                constraints=constraints.get("optimization", {}),
            )
        else:
            asset_list = [
                {"symbol": ac.value, "expected_return": ad.get("expected_return", 0.06), "volatility": ad.get("volatility", 0.15)}
                for ac, ad in asset_data.items()
            ]
            optimization = self.optimizer.optimize(assets=asset_list)

        # Step 4: Risk Budget
        budget_entities = []
        for ac, ad in asset_data.items():
            budget_entities.append(
                {
                    "entity_id": ac.value,
                    "level": BudgetLevel.ASSET_CLASS.value,
                    "volatility": ad.get("volatility", 0.15),
                    "sharpe": ad.get("sharpe", 0.5),
                }
            )
        # Add position-level budgets
        if position_data:
            for p in position_data:
                budget_entities.append(
                    {
                        "entity_id": p.get("symbol", "unknown"),
                        "level": BudgetLevel.POSITION.value,
                        "volatility": p.get("volatility", 0.15),
                        "sharpe": p.get("sharpe", 0.5),
                    }
                )

        budget = self.budget_engine.allocate(
            entities=budget_entities,
            consumption=constraints.get("risk_consumption", {}),
        )

        # Step 5: Exposure Analysis
        exposure = None
        if position_data:
            exposure = self.exposure_engine.analyze(
                positions=position_data,
                nav=nav,
            )

        # Step 6: Rebalancing Plan
        rebalance = None
        if current_weights:
            target_w = target_weights or allocation.to_dict()
            rebalance = self.rebalancer.plan(
                current_weights=current_weights,
                target_weights=target_w,
            )

        # Step 7: Attribution
        attribution = None
        if benchmark_data:
            attribution = self.attributor.attribute(
                portfolio_data={
                    "total_return": optimization.expected_return,
                    "weights": current_weights or allocation.to_dict(),
                    "returns": {
                        ac.value: ad.get("expected_return", 0.06)
                        for ac, ad in asset_data.items()
                    },
                },
                benchmark_data=benchmark_data,
            )

        # Step 8: Record to memory
        self.memory.record(
            event_type=MemoryEventType.ALLOCATION_CHANGE,
            data={"weights": allocation.to_dict(), "strategy": allocation.strategy.value},
            tags=["allocation", allocation.strategy.value],
        )

        # Build summary
        summary = self._build_summary(allocation, sizing, budget, exposure, rebalance, attribution)

        return PortfolioBuildResult(
            allocation=allocation,
            sizing=sizing,
            budget=budget,
            optimization=optimization,
            exposure=exposure,
            rebalance=rebalance,
            attribution=attribution,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Summary Builder
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        allocation: Optional[AllocationResult],
        sizing: Optional[SizingResult],
        budget: Optional[BudgetAllocation],
        exposure: Optional[ExposureReport],
        rebalance: Optional[RebalancePlan],
        attribution: Optional[AttributionResult],
    ) -> dict[str, Any]:
        """Build a comprehensive summary dict."""
        summary: dict[str, Any] = {
            "health_checks": [],
            "warnings": [],
            "actions": [],
        }

        # Allocation
        if allocation:
            summary["allocation"] = {
                "strategy": allocation.strategy.value,
                "weights": allocation.to_dict(),
                "diversification": round(allocation.diversification_ratio, 4),
            }
            if not allocation.is_valid:
                summary["warnings"].append("Allocation weights do not sum to 1.0")

        # Sizing
        if sizing:
            summary["sizing"] = {
                "total_allocation": round(sizing.total_allocation, 4),
                "remaining_capital": round(sizing.remaining_capital, 4),
                "concentration": round(sizing.concentration_ratio, 4),
            }
            if sizing.concentration_ratio > 0.5:
                summary["warnings"].append(f"High position concentration: {sizing.concentration_ratio:.2%}")

        # Budget
        if budget:
            summary["budget"] = {
                "total": budget.total_risk_budget,
                "unused": round(budget.unused_budget, 4),
                "exceeded": len(budget.exceeded_budgets),
            }
            for b in budget.exceeded_budgets:
                summary["warnings"].append(f"Risk budget exceeded: {b.entity_id} ({b.utilization:.1%})")

        # Exposure
        if exposure:
            summary["exposure"] = {
                "gross_exposure": round(exposure.total_gross_exposure, 2),
                "leverage": round(exposure.leverage_ratio, 2),
                "breaches": exposure.breached_exposures,
            }
            for e in exposure.exposures:
                if e.is_breached:
                    summary["warnings"].append(f"Exposure breach: {e.exposure_type.value} at {e.utilization:.1%}")

        # Rebalance
        if rebalance:
            summary["rebalance"] = {
                "status": rebalance.status.value,
                "trades": rebalance.trade_count,
                "turnover": round(rebalance.total_turnover, 4),
            }
            if rebalance.status.value == "critical":
                summary["actions"].append("Immediate rebalancing required")
            elif rebalance.status.value == "action_required":
                summary["actions"].append("Rebalancing recommended")

        # Attribution
        if attribution:
            summary["attribution"] = {
                "excess_return_bps": round(attribution.excess_return_bps, 2),
            }

        # Health checks
        if not summary["warnings"]:
            summary["health_checks"].append("All systems nominal")

        return summary

    # ------------------------------------------------------------------
    # Quick Methods
    # ------------------------------------------------------------------

    def quick_build(
        self,
        asset_data: Optional[dict[str, dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Quick portfolio build with minimal input.

        Args:
            asset_data: Simple dict mapping asset name to {return, volatility}.

        Returns:
            Dict with key portfolio metrics.
        """
        converted: dict[AssetClass, dict[str, Any]] = {}
        for name, data in (asset_data or {}).items():
            try:
                ac = AssetClass(name.lower())
            except ValueError:
                continue
            converted[ac] = data

        result = self.build(asset_data=converted)

        return {
            "allocation": result.allocation.to_dict() if result.allocation else {},
            "budget_summary": result.budget.to_dict() if result.budget else {},
            "is_healthy": result.is_healthy,
            "summary": result.summary,
        }

    def clear_all(self) -> None:
        """Reset all engines' history."""
        self.allocator.clear()
        self.sizer.clear()
        self.budget_engine.clear()
        self.exposure_engine.clear()
        self.optimizer.clear()
        self.rebalancer.clear()
        self.attributor.clear()
        self.memory.clear()
