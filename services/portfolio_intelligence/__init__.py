"""AI Portfolio Intelligence Engine — v0.4.0.

Comprehensive portfolio management with AI-driven intelligence across
9 capability modules:

Sub-modules:
  - allocation:  AssetAllocationEngine — strategic & tactical allocation
  - sizing:      PositionSizingEngine — risk-based position sizing
  - budget:      RiskBudgetEngine — hierarchical risk budget management
  - exposure:    ExposureEngine — multi-dimensional exposure monitoring
  - optimizer:   PortfolioOptimizer — multi-objective optimization
  - rebalance:   RebalanceEngine — intelligent rebalancing plans
  - attribution: AttributionEngine — performance return decomposition
  - memory:      PortfolioMemory — decision history & analytics
  - service:     PortfolioIntelligenceService — unified orchestration API
"""

from services.portfolio_intelligence.allocation import (
    AssetAllocation,
    AssetAllocationEngine,
    AssetClass,
    AllocationResult,
    AllocationStrategy,
    Horizon,
    RiskTolerance,
)
from services.portfolio_intelligence.attribution import (
    AttributionComponent,
    AttributionEngine,
    AttributionLevel,
    AttributionMethod,
    AttributionResult,
)
from services.portfolio_intelligence.budget import (
    BudgetAllocation,
    BudgetLevel,
    BudgetMethod,
    BudgetStatus,
    RiskBudget,
    RiskBudgetEngine,
)
from services.portfolio_intelligence.exposure import (
    Exposure,
    ExposureDirection,
    ExposureEngine,
    ExposureReport,
    ExposureStatus,
    ExposureType,
)
from services.portfolio_intelligence.memory import (
    DecisionOutcome,
    MemoryEvent,
    MemoryEventType,
    PerformanceSnapshot,
    PortfolioInsight,
    PortfolioMemory,
)
from services.portfolio_intelligence.optimizer import (
    ConstraintType,
    EfficientFrontierPoint,
    Objective,
    OptimizationConstraint,
    OptimizationResult,
    PortfolioOptimizer,
)
from services.portfolio_intelligence.rebalance import (
    RebalanceEngine,
    RebalancePlan,
    RebalanceStatus,
    RebalanceStrategy,
    RebalanceTrade,
    TradeSide,
)
from services.portfolio_intelligence.sizing import (
    PositionSize,
    PositionSizingEngine,
    SizingMethod,
    SizingPriority,
    SizingResult,
)
from services.portfolio_intelligence.service import (
    PortfolioBuildResult,
    PortfolioIntelligenceService,
)

__all__ = [
    # allocation
    "AssetAllocation",
    "AssetAllocationEngine",
    "AssetClass",
    "AllocationResult",
    "AllocationStrategy",
    "Horizon",
    "RiskTolerance",
    # sizing
    "PositionSize",
    "PositionSizingEngine",
    "SizingMethod",
    "SizingPriority",
    "SizingResult",
    # budget
    "BudgetAllocation",
    "BudgetLevel",
    "BudgetMethod",
    "BudgetStatus",
    "RiskBudget",
    "RiskBudgetEngine",
    # exposure
    "Exposure",
    "ExposureDirection",
    "ExposureEngine",
    "ExposureReport",
    "ExposureStatus",
    "ExposureType",
    # optimizer
    "ConstraintType",
    "EfficientFrontierPoint",
    "Objective",
    "OptimizationConstraint",
    "OptimizationResult",
    "PortfolioOptimizer",
    # rebalance
    "RebalanceEngine",
    "RebalancePlan",
    "RebalanceStatus",
    "RebalanceStrategy",
    "RebalanceTrade",
    "TradeSide",
    # attribution
    "AttributionComponent",
    "AttributionEngine",
    "AttributionLevel",
    "AttributionMethod",
    "AttributionResult",
    # memory
    "DecisionOutcome",
    "MemoryEvent",
    "MemoryEventType",
    "PerformanceSnapshot",
    "PortfolioInsight",
    "PortfolioMemory",
    # service
    "PortfolioBuildResult",
    "PortfolioIntelligenceService",
]
