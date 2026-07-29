"""
Portfolio Construction Models

Core dataclasses for the Portfolio Construction Engine.
Defines portfolio, allocation, constraint, and risk budget objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# =============================================================================
# Enums (must be defined before dataclasses that reference them)
# =============================================================================


class AllocationReason(Enum):
    """Reason for a particular allocation."""

    OPTIMIZATION = "optimization"
    RISK_PARITY = "risk_parity"
    EQUAL_WEIGHT = "equal_weight"
    MANUAL = "manual"
    DYNAMIC_ADJUSTMENT = "dynamic_adjustment"
    REBALANCE = "rebalance"
    RISK_REDUCTION = "risk_reduction"
    CONSTRAINT_ENFORCED = "constraint_enforced"
    CASH_RESERVE = "cash_reserve"


class OptimizationMethod(Enum):
    """Portfolio optimization methods."""

    MEAN_VARIANCE = "mean_variance"
    RISK_PARITY = "risk_parity"
    EQUAL_WEIGHT = "equal_weight"
    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance"
    MAX_DIVERSIFICATION = "max_diversification"
    BLACK_LITTERMAN = "black_litterman"
    CUSTOM = "custom"


class RebalanceAction(Enum):
    """Action to take for a strategy position."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    REMOVE = "remove"
    ADD = "add"


# =============================================================================
# Forward declarations for circular references
# =============================================================================

# StrategySnapshot is needed by StrategyAllocation
# StrategyAllocation is needed by Portfolio
# etc.


# =============================================================================
# Constraints (referenced by many classes)
# =============================================================================


@dataclass
class WeightConstraint:
    """Weight limits for a single strategy."""

    strategy_id: str
    min_weight: float = 0.0
    max_weight: float = 1.0
    step_size: float = 0.01  # minimum increment for weight changes


@dataclass
class RiskConstraint:
    """Risk limits for a single strategy."""

    strategy_id: str
    max_volatility: float = float("inf")  # annualized
    max_drawdown: float = float("inf")  # e.g. 0.15 = 15%
    max_var_95: Optional[float] = None  # Value-at-Risk at 95%
    max_cvar_95: Optional[float] = None  # Conditional VaR at 95%
    max_risk_contribution: float = 1.0  # max share of total portfolio risk


@dataclass
class FactorExposureConstraint:
    """Limits on factor exposures."""

    factor_name: str
    max_exposure: float = 1.0
    min_exposure: float = -1.0


@dataclass
class SectorExposureConstraint:
    """Limits on sector exposures."""

    sector_name: str
    max_exposure: float = 1.0
    min_exposure: float = 0.0


@dataclass
class DrawdownConstraint:
    """Portfolio-level drawdown limit."""

    max_drawdown: float = 0.20  # 20% max drawdown
    max_rolling_drawdown_days: int = 60


@dataclass
class PortfolioConstraints:
    """Aggregate constraints for portfolio construction."""

    weight_constraints: Dict[str, WeightConstraint] = field(default_factory=dict)
    risk_constraints: Dict[str, RiskConstraint] = field(default_factory=dict)
    factor_constraints: Dict[str, FactorExposureConstraint] = field(default_factory=dict)
    sector_constraints: Dict[str, SectorExposureConstraint] = field(default_factory=dict)
    drawdown_constraint: Optional[DrawdownConstraint] = None
    max_total_weight: float = 1.0
    min_total_weight: float = 0.0
    max_single_strategy_weight: float = 0.5
    min_single_strategy_weight: float = 0.0
    max_strategies: int = 20
    min_strategies: int = 1


# =============================================================================
# Risk Budget (referenced by allocation models)
# =============================================================================


@dataclass
class RiskBudgetAllocation:
    """Risk budget assigned to a specific strategy."""

    strategy_id: str
    risk_budget: float = 0.0
    risk_used: float = 0.0
    risk_remaining: float = 0.0
    marginal_risk: float = 0.0  # marginal contribution to portfolio risk
    percentage_of_total: float = 0.0


@dataclass
class RiskBudget:
    """Risk budget for a strategy or the entire portfolio."""

    budget_id: str
    total_risk_budget: float = 0.0  # in risk units (e.g. variance)
    allocated_risk: float = 0.0
    remaining_risk: float = 0.0
    risk_unit: str = "variance"  # variance, std_dev, var, cvar

    @property
    def utilization(self) -> float:
        if self.total_risk_budget == 0:
            return 0.0
        return self.allocated_risk / self.total_risk_budget


# =============================================================================
# Exposure (referenced by allocation models)
# =============================================================================


@dataclass
class FactorExposure:
    """Factor exposure information."""

    factor_name: str
    exposure: float = 0.0
    contribution_to_risk: float = 0.0
    limit: float = float("inf")


@dataclass
class SectorExposure:
    """Sector exposure information."""

    sector_name: str
    exposure: float = 0.0
    contribution_to_risk: float = 0.0
    limit: float = float("inf")


@dataclass
class ExposureReport:
    """Full exposure report for a portfolio."""

    portfolio_id: str
    factor_exposures: Dict[str, FactorExposure] = field(default_factory=dict)
    sector_exposures: Dict[str, SectorExposure] = field(default_factory=dict)
    total_factor_risk: float = 0.0
    total_sector_risk: float = 0.0
    concentration_warnings: List[str] = field(default_factory=list)


# =============================================================================
# Strategy Profile
# =============================================================================


@dataclass
class StrategySnapshot:
    """Snapshot of strategy performance for allocation decisions."""

    strategy_id: str
    name: str = ""
    expected_return: float = 0.0  # annualized
    expected_volatility: float = 0.0  # annualized
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    recent_alpha: float = 0.0  # recent alpha in bps
    recent_returns: List[float] = field(default_factory=list)
    win_rate: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    current_weight: float = 0.0
    factor_exposures: Dict[str, float] = field(default_factory=dict)
    sector_exposures: Dict[str, float] = field(default_factory=dict)
    correlation_to_portfolio: float = 0.0
    tracking_error: float = 0.0


@dataclass
class StrategyProfile:
    """Full strategy profile used during construction."""

    strategy_id: str
    name: str
    snapshot: StrategySnapshot
    weight_constraint: Optional[WeightConstraint] = None
    risk_constraint: Optional[RiskConstraint] = None


# =============================================================================
# Allocation
# =============================================================================


@dataclass
class StrategyAllocation:
    """Allocation for a single strategy within the portfolio."""

    strategy_id: str
    strategy_name: str = ""
    target_weight: float = 0.0
    current_weight: float = 0.0
    capital_allocated: float = 0.0
    expected_return_contribution: float = 0.0
    risk_contribution: float = 0.0  # percentage of total risk
    risk_budget_used: float = 0.0
    reason: AllocationReason = AllocationReason.OPTIMIZATION
    constraints_hit: List[str] = field(default_factory=list)


@dataclass
class OptimizationMetrics:
    """Metrics produced by optimization."""

    method: OptimizationMethod = OptimizationMethod.MEAN_VARIANCE
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    diversification_ratio: float = 0.0
    effective_n: float = 0.0  # effective number of strategies
    herfindahl_index: float = 0.0  # concentration measure
    turnover: float = 0.0
    iterations: int = 0
    converged: bool = False
    optimization_time_ms: float = 0.0


@dataclass
class OptimizationResult:
    """Full optimization output."""

    portfolio_id: str
    method: OptimizationMethod
    weights: Dict[str, float] = field(default_factory=dict)
    metrics: OptimizationMetrics = field(default_factory=OptimizationMetrics)
    status: str = "success"
    message: str = ""
    iterations: int = 0


@dataclass
class RebalanceDecision:
    """Decision for rebalancing a single strategy."""

    strategy_id: str
    action: RebalanceAction = RebalanceAction.HOLD
    current_weight: float = 0.0
    target_weight: float = 0.0
    weight_delta: float = 0.0
    capital_delta: float = 0.0
    reason: str = ""


@dataclass
class AllocationResult:
    """Result of a portfolio allocation run."""

    portfolio_id: str
    allocations: Dict[str, StrategyAllocation] = field(default_factory=dict)
    cash_weight: float = 0.0
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    expected_sharpe: float = 0.0
    optimization_metrics: Optional[OptimizationMetrics] = None
    risk_budget_allocations: Dict[str, RiskBudgetAllocation] = field(default_factory=dict)
    exposure_report: Optional[ExposureReport] = None
    constraint_violations: List[str] = field(default_factory=list)
    rebalance_needed: bool = False
    rebalance_decisions: List[RebalanceDecision] = field(default_factory=list)
    method: OptimizationMethod = OptimizationMethod.MEAN_VARIANCE
    timestamp: str = ""


# =============================================================================
# Portfolio (depends on allocation models)
# =============================================================================


@dataclass
class PortfolioConfig:
    """Configuration for a portfolio construction request."""

    portfolio_id: str
    name: str = ""
    capital: float = 0.0
    base_currency: str = "USD"
    risk_free_rate: float = 0.0
    risk_aversion: float = 1.0  # lambda in utility function
    max_leverage: float = 1.0
    min_cash_weight: float = 0.0
    rebalance_threshold: float = 0.05  # 5% drift triggers rebalance
    lookback_days: int = 60
    target_volatility: Optional[float] = None


@dataclass
class Portfolio:
    """A constructed portfolio with strategy allocations."""

    portfolio_id: str
    capital: float
    strategy_allocations: List[StrategyAllocation] = field(default_factory=list)
    target_weights: Dict[str, float] = field(default_factory=dict)
    current_weights: Dict[str, float] = field(default_factory=dict)
    cash_weight: float = 0.0
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    expected_sharpe: float = 0.0
    risk_budget: Dict[str, float] = field(default_factory=dict)
    constraints: Optional[PortfolioConstraints] = None
    optimization_method: Optional[OptimizationMethod] = None

    @property
    def total_weight(self) -> float:
        return sum(self.target_weights.values()) + self.cash_weight

    @property
    def active_strategies(self) -> int:
        return len([w for w in self.target_weights.values() if w > 0])
