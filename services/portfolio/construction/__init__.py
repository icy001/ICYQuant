"""
Portfolio Construction Engine

Provides the capital allocation layer between strategy signals and order execution.
Supports multi-strategy portfolio construction with:
- Mean-Variance Optimization
- Risk Parity allocation
- Dynamic weight rebalancing
- Risk budget enforcement
- Factor/sector exposure constraints
"""

from .models import (
    # Portfolio
    Portfolio,
    PortfolioConfig,
    # Allocation
    StrategyAllocation,
    AllocationResult,
    AllocationReason,
    # Constraints
    WeightConstraint,
    RiskConstraint,
    FactorExposureConstraint,
    SectorExposureConstraint,
    DrawdownConstraint,
    PortfolioConstraints,
    # Optimization
    OptimizationMethod,
    OptimizationResult,
    OptimizationMetrics,
    # Strategy
    StrategyProfile,
    StrategySnapshot,
    # Rebalance
    RebalanceDecision,
    RebalanceAction,
    # Risk
    RiskBudget,
    RiskBudgetAllocation,
    # Exposure
    FactorExposure,
    SectorExposure,
    ExposureReport,
)

from .constraints import (
    ConstraintValidator,
    ConstraintEnforcer,
)

from .optimizer import (
    PortfolioOptimizer,
    MeanVarianceOptimizer,
    RiskParityOptimizer,
)

from .allocator import (
    DynamicAllocator,
    RebalanceEngine,
)

from .service import (
    PortfolioConstructionService,
)

__all__ = [
    # Models
    "Portfolio",
    "PortfolioConfig",
    "StrategyAllocation",
    "AllocationResult",
    "AllocationReason",
    "WeightConstraint",
    "RiskConstraint",
    "FactorExposureConstraint",
    "SectorExposureConstraint",
    "DrawdownConstraint",
    "PortfolioConstraints",
    "OptimizationMethod",
    "OptimizationResult",
    "OptimizationMetrics",
    "StrategyProfile",
    "StrategySnapshot",
    "RebalanceDecision",
    "RebalanceAction",
    "RiskBudget",
    "RiskBudgetAllocation",
    "FactorExposure",
    "SectorExposure",
    "ExposureReport",
    # Constraints
    "ConstraintValidator",
    "ConstraintEnforcer",
    # Optimizers
    "PortfolioOptimizer",
    "MeanVarianceOptimizer",
    "RiskParityOptimizer",
    # Allocation
    "DynamicAllocator",
    "RebalanceEngine",
    # Service
    "PortfolioConstructionService",
]
