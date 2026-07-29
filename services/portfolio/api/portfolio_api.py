"""
Portfolio Construction API

REST endpoints for portfolio construction:
- POST /build - Build a portfolio from strategy data
- POST /build/multi - Build from multiple strategies
- POST /rebalance - Rebalance an existing portfolio
- GET /portfolio/{id} - Get portfolio details
- POST /constraints/validate - Validate constraints
- POST /risk/allocate - Allocate risk budget
"""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


# =============================================================================
# Request / Response Models
# =============================================================================


class StrategyData(BaseModel):
    """Strategy data for portfolio construction."""

    strategy_id: str
    name: str = ""
    expected_return: float = 0.0
    expected_volatility: float = 0.15
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    recent_alpha: float = 0.0
    win_rate: float = 0.5
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    current_weight: float = 0.0
    factor_exposures: Dict[str, float] = Field(default_factory=dict)
    sector_exposures: Dict[str, float] = Field(default_factory=dict)
    correlation_to_portfolio: float = 0.3
    tracking_error: float = 0.0


class BuildRequest(BaseModel):
    """Request to build a portfolio."""

    portfolio_id: str = Field(..., description="Portfolio identifier")
    capital: float = Field(..., gt=0, description="Total capital")
    strategies: List[StrategyData] = Field(..., min_items=1)
    method: str = Field(default="mean_variance", description="Optimization method")
    cash_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_free_rate: float = Field(default=0.0)


class WeightConstraintData(BaseModel):
    strategy_id: str
    min_weight: float = 0.0
    max_weight: float = 1.0


class RiskConstraintData(BaseModel):
    strategy_id: str
    max_volatility: float = float("inf")
    max_drawdown: float = float("inf")
    max_risk_contribution: float = 1.0


class FactorConstraintData(BaseModel):
    factor_name: str
    max_exposure: float = 1.0
    min_exposure: float = -1.0


class SectorConstraintData(BaseModel):
    sector_name: str
    max_exposure: float = 1.0
    min_exposure: float = 0.0


class ConstraintsData(BaseModel):
    """Portfolio constraints."""

    weight_constraints: List[WeightConstraintData] = Field(default_factory=list)
    risk_constraints: List[RiskConstraintData] = Field(default_factory=list)
    factor_constraints: List[FactorConstraintData] = Field(default_factory=list)
    sector_constraints: List[SectorConstraintData] = Field(default_factory=list)
    max_single_strategy_weight: float = 0.5
    min_single_strategy_weight: float = 0.0
    max_strategies: int = 20
    min_strategies: int = 1


class BuildWithConstraintsRequest(BuildRequest):
    """Build portfolio with constraints."""

    constraints: Optional[ConstraintsData] = None


class RebalanceRequest(BaseModel):
    """Request to rebalance a portfolio."""

    portfolio_id: str
    capital: float = Field(..., gt=0)
    current_weights: Dict[str, float] = Field(..., description="Current strategy weights")
    strategies: List[StrategyData] = Field(..., min_items=1)
    method: str = "mean_variance"
    threshold: float = Field(default=0.02, description="Rebalance threshold")


class RiskAllocateRequest(BaseModel):
    """Request to allocate risk budget."""

    portfolio_id: str
    total_risk_budget: float = 1.0
    strategies: List[StrategyData] = Field(..., min_items=1)
    method: str = "equal_risk"


# =============================================================================
# Response Models
# =============================================================================


class AllocationResponse(BaseModel):
    strategy_id: str
    strategy_name: str
    target_weight: float
    current_weight: float
    capital_allocated: float
    reason: str
    risk_contribution: float = 0.0


class PortfolioResponse(BaseModel):
    portfolio_id: str
    capital: float
    allocations: List[AllocationResponse]
    cash_weight: float
    expected_return: float
    expected_volatility: float
    expected_sharpe: float
    optimization_method: str
    risk_budget: Dict[str, float] = Field(default_factory=dict)
    constraint_violations: List[str] = Field(default_factory=list)
    rebalance_needed: bool = False
    rebalance_decisions: List[Dict] = Field(default_factory=list)


class RebalanceDecisionResponse(BaseModel):
    strategy_id: str
    action: str
    current_weight: float
    target_weight: float
    weight_delta: float
    capital_delta: float
    reason: str


class RebalanceResponse(BaseModel):
    portfolio_id: str
    portfolio: PortfolioResponse
    rebalance_decisions: List[RebalanceDecisionResponse]
    turnover: float


class RiskBudgetResponse(BaseModel):
    strategy_id: str
    risk_budget: float
    risk_used: float
    risk_remaining: float
    percentage_of_total: float


class RiskAllocateResponse(BaseModel):
    portfolio_id: str
    total_risk_budget: float
    allocations: List[RiskBudgetResponse]
    total_utilization: float


class ConstraintValidationResponse(BaseModel):
    is_valid: bool
    violations: List[str]


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/build", response_model=PortfolioResponse)
async def build_portfolio(request: BuildRequest):
    """
    Build a portfolio from strategy performance data.

    Accepts strategy snapshots (returns, volatility, Sharpe, etc.)
    and produces optimal target weights through the specified
    optimization method.
    """
    from services.portfolio.construction.service import PortfolioConstructionService
    from services.portfolio.construction.models import OptimizationMethod

    method_map = {
        "mean_variance": OptimizationMethod.MEAN_VARIANCE,
        "risk_parity": OptimizationMethod.RISK_PARITY,
        "equal_weight": OptimizationMethod.EQUAL_WEIGHT,
        "max_sharpe": OptimizationMethod.MAX_SHARPE,
        "min_variance": OptimizationMethod.MIN_VARIANCE,
    }

    method = method_map.get(request.method, OptimizationMethod.MEAN_VARIANCE)

    service = PortfolioConstructionService()

    try:
        portfolio = service.build_multi(
            portfolio_id=request.portfolio_id,
            capital=request.capital,
            strategies_data=[s.dict() for s in request.strategies],
            method=method,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    allocations = []
    for alloc in portfolio.strategy_allocations:
        allocations.append(AllocationResponse(
            strategy_id=alloc.strategy_id,
            strategy_name=alloc.strategy_name,
            target_weight=alloc.target_weight,
            current_weight=alloc.current_weight,
            capital_allocated=alloc.capital_allocated,
            reason=alloc.reason.value,
            risk_contribution=alloc.risk_contribution,
        ))

    return PortfolioResponse(
        portfolio_id=portfolio.portfolio_id,
        capital=portfolio.capital,
        allocations=allocations,
        cash_weight=portfolio.cash_weight,
        expected_return=portfolio.expected_return,
        expected_volatility=portfolio.expected_volatility,
        expected_sharpe=portfolio.expected_sharpe,
        optimization_method=method.value,
        risk_budget=portfolio.risk_budget,
    )


@router.post("/build/multi", response_model=PortfolioResponse)
async def build_portfolio_multi(request: BuildWithConstraintsRequest):
    """
    Build a portfolio with full constraint specification.

    Supports all constraint types:
    - Weight limits per strategy
    - Risk limits (volatility, drawdown)
    - Factor exposure limits
    - Sector exposure limits
    """
    from services.portfolio.construction.service import PortfolioConstructionService
    from services.portfolio.construction.models import (
        OptimizationMethod,
        PortfolioConstraints,
        WeightConstraint,
        RiskConstraint,
        FactorExposureConstraint,
        SectorExposureConstraint,
    )

    method_map = {
        "mean_variance": OptimizationMethod.MEAN_VARIANCE,
        "risk_parity": OptimizationMethod.RISK_PARITY,
        "equal_weight": OptimizationMethod.EQUAL_WEIGHT,
        "max_sharpe": OptimizationMethod.MAX_SHARPE,
        "min_variance": OptimizationMethod.MIN_VARIANCE,
    }
    method = method_map.get(request.method, OptimizationMethod.MEAN_VARIANCE)

    # Build constraints
    constraints = None
    if request.constraints:
        weight_constraints = {
            wc.strategy_id: WeightConstraint(
                strategy_id=wc.strategy_id,
                min_weight=wc.min_weight,
                max_weight=wc.max_weight,
            )
            for wc in request.constraints.weight_constraints
        }
        risk_constraints = {
            rc.strategy_id: RiskConstraint(
                strategy_id=rc.strategy_id,
                max_volatility=rc.max_volatility,
                max_drawdown=rc.max_drawdown,
                max_risk_contribution=rc.max_risk_contribution,
            )
            for rc in request.constraints.risk_constraints
        }
        factor_constraints = {
            fc.factor_name: FactorExposureConstraint(
                factor_name=fc.factor_name,
                max_exposure=fc.max_exposure,
                min_exposure=fc.min_exposure,
            )
            for fc in request.constraints.factor_constraints
        }
        sector_constraints = {
            sc.sector_name: SectorExposureConstraint(
                sector_name=sc.sector_name,
                max_exposure=sc.max_exposure,
                min_exposure=sc.min_exposure,
            )
            for sc in request.constraints.sector_constraints
        }

        constraints = PortfolioConstraints(
            weight_constraints=weight_constraints,
            risk_constraints=risk_constraints,
            factor_constraints=factor_constraints,
            sector_constraints=sector_constraints,
            max_single_strategy_weight=request.constraints.max_single_strategy_weight,
            min_single_strategy_weight=request.constraints.min_single_strategy_weight,
            max_strategies=request.constraints.max_strategies,
            min_strategies=request.constraints.min_strategies,
        )

    service = PortfolioConstructionService()

    try:
        portfolio = service.build_multi(
            portfolio_id=request.portfolio_id,
            capital=request.capital,
            strategies_data=[s.dict() for s in request.strategies],
            constraints=constraints,
            method=method,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    allocations = []
    for alloc in portfolio.strategy_allocations:
        allocations.append(AllocationResponse(
            strategy_id=alloc.strategy_id,
            strategy_name=alloc.strategy_name,
            target_weight=alloc.target_weight,
            current_weight=alloc.current_weight,
            capital_allocated=alloc.capital_allocated,
            reason=alloc.reason.value,
            risk_contribution=alloc.risk_contribution,
        ))

    return PortfolioResponse(
        portfolio_id=portfolio.portfolio_id,
        capital=portfolio.capital,
        allocations=allocations,
        cash_weight=portfolio.cash_weight,
        expected_return=portfolio.expected_return,
        expected_volatility=portfolio.expected_volatility,
        expected_sharpe=portfolio.expected_sharpe,
        optimization_method=method.value,
        risk_budget=portfolio.risk_budget,
    )


@router.post("/rebalance", response_model=RebalanceResponse)
async def rebalance_portfolio(request: RebalanceRequest):
    """
    Rebalance an existing portfolio.

    Compares current weights to optimized target weights and
    generates BUY/SELL/HOLD decisions with capital deltas.
    """
    from services.portfolio.construction.service import PortfolioConstructionService
    from services.portfolio.construction.models import OptimizationMethod, Portfolio

    method_map = {
        "mean_variance": OptimizationMethod.MEAN_VARIANCE,
        "risk_parity": OptimizationMethod.RISK_PARITY,
        "equal_weight": OptimizationMethod.EQUAL_WEIGHT,
        "max_sharpe": OptimizationMethod.MAX_SHARPE,
        "min_variance": OptimizationMethod.MIN_VARIANCE,
    }
    method = method_map.get(request.method, OptimizationMethod.MEAN_VARIANCE)

    service = PortfolioConstructionService()

    try:
        # Build target portfolio
        new_portfolio = service.build_multi(
            portfolio_id=request.portfolio_id,
            capital=request.capital,
            strategies_data=[s.dict() for s in request.strategies],
            method=method,
        )

        # Compute rebalance decisions
        rebalance_engine = service.rebalance_engine
        rebalance_engine.threshold = request.threshold

        decisions = rebalance_engine.compute_decisions(
            current_weights=request.current_weights,
            target_weights=new_portfolio.target_weights,
            capital=request.capital,
        )

        turnover = rebalance_engine.calculate_turnover(
            request.current_weights,
            new_portfolio.target_weights,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    allocations = []
    for alloc in new_portfolio.strategy_allocations:
        allocations.append(AllocationResponse(
            strategy_id=alloc.strategy_id,
            strategy_name=alloc.strategy_name,
            target_weight=alloc.target_weight,
            current_weight=alloc.current_weight,
            capital_allocated=alloc.capital_allocated,
            reason=alloc.reason.value,
        ))

    decision_responses = [
        RebalanceDecisionResponse(
            strategy_id=d.strategy_id,
            action=d.action.value,
            current_weight=d.current_weight,
            target_weight=d.target_weight,
            weight_delta=d.weight_delta,
            capital_delta=d.capital_delta,
            reason=d.reason,
        )
        for d in decisions
    ]

    return RebalanceResponse(
        portfolio_id=request.portfolio_id,
        portfolio=PortfolioResponse(
            portfolio_id=new_portfolio.portfolio_id,
            capital=new_portfolio.capital,
            allocations=allocations,
            cash_weight=new_portfolio.cash_weight,
            expected_return=new_portfolio.expected_return,
            expected_volatility=new_portfolio.expected_volatility,
            expected_sharpe=new_portfolio.expected_sharpe,
            optimization_method=method.value,
            risk_budget=new_portfolio.risk_budget,
        ),
        rebalance_decisions=decision_responses,
        turnover=turnover,
    )


@router.post("/constraints/validate", response_model=ConstraintValidationResponse)
async def validate_constraints(request: BuildWithConstraintsRequest):
    """Validate weights against constraints without building."""
    from services.portfolio.construction.constraints import ConstraintValidator
    from services.portfolio.construction.models import (
        PortfolioConstraints,
        WeightConstraint,
        RiskConstraint,
        FactorExposureConstraint,
        SectorExposureConstraint,
        StrategySnapshot,
    )

    validator = ConstraintValidator()

    # Build constraints
    constraints = None
    if request.constraints:
        weight_constraints = {
            wc.strategy_id: WeightConstraint(
                strategy_id=wc.strategy_id,
                min_weight=wc.min_weight,
                max_weight=wc.max_weight,
            )
            for wc in request.constraints.weight_constraints
        }
        risk_constraints = {
            rc.strategy_id: RiskConstraint(
                strategy_id=rc.strategy_id,
                max_volatility=rc.max_volatility,
                max_drawdown=rc.max_drawdown,
            )
            for rc in request.constraints.risk_constraints
        }
        factor_constraints = {
            fc.factor_name: FactorExposureConstraint(
                factor_name=fc.factor_name,
                max_exposure=fc.max_exposure,
                min_exposure=fc.min_exposure,
            )
            for fc in request.constraints.factor_constraints
        }
        sector_constraints = {
            sc.sector_name: SectorExposureConstraint(
                sector_name=sc.sector_name,
                max_exposure=sc.max_exposure,
                min_exposure=sc.min_exposure,
            )
            for sc in request.constraints.sector_constraints
        }
        constraints = PortfolioConstraints(
            weight_constraints=weight_constraints,
            risk_constraints=risk_constraints,
            factor_constraints=factor_constraints,
            sector_constraints=sector_constraints,
            max_single_strategy_weight=request.constraints.max_single_strategy_weight,
            min_single_strategy_weight=request.constraints.min_single_strategy_weight,
            max_strategies=request.constraints.max_strategies,
            min_strategies=request.constraints.min_strategies,
        )

    # Build snapshots
    snapshots = {}
    for s in request.strategies:
        snapshots[s.strategy_id] = StrategySnapshot(
            strategy_id=s.strategy_id,
            name=s.name,
            expected_return=s.expected_return,
            expected_volatility=s.expected_volatility,
            max_drawdown=s.max_drawdown,
            factor_exposures=s.factor_exposures,
            sector_exposures=s.sector_exposures,
        )

    # Equal weights for validation
    n = len(snapshots)
    weights = {sid: 1.0 / n for sid in snapshots}

    violations = validator.validate(weights, snapshots, constraints)
    is_valid = len(violations) == 0

    return ConstraintValidationResponse(
        is_valid=is_valid,
        violations=violations,
    )


@router.post("/risk/allocate", response_model=RiskAllocateResponse)
async def allocate_risk_budget(request: RiskAllocateRequest):
    """Allocate risk budget across strategies."""
    from services.portfolio.risk.budget import RiskBudgetManager
    from services.portfolio.construction.models import StrategySnapshot

    manager = RiskBudgetManager(total_risk_budget=request.total_risk_budget)

    snapshots = {}
    for s in request.strategies:
        snapshots[s.strategy_id] = StrategySnapshot(
            strategy_id=s.strategy_id,
            name=s.name,
            expected_volatility=s.expected_volatility,
        )

    allocations = manager.allocate(snapshots, method=request.method)
    utilization = manager.get_total_utilization(allocations)

    budget_responses = [
        RiskBudgetResponse(
            strategy_id=a.strategy_id,
            risk_budget=a.risk_budget,
            risk_used=a.risk_used,
            risk_remaining=a.risk_remaining,
            percentage_of_total=a.percentage_of_total,
        )
        for a in allocations.values()
    ]

    return RiskAllocateResponse(
        portfolio_id=request.portfolio_id,
        total_risk_budget=request.total_risk_budget,
        allocations=budget_responses,
        total_utilization=utilization,
    )
