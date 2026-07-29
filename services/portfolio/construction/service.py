"""
Portfolio Construction Service

Orchestrates the full portfolio construction workflow:
1. Accept strategy performance data
2. Run optimization
3. Enforce constraints
4. Generate allocations
5. Compute rebalance decisions
6. Return portfolio

Acts as the main entry point for the Portfolio Construction Engine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from .models import (
    AllocationResult,
    OptimizationMethod,
    Portfolio,
    PortfolioConfig,
    PortfolioConstraints,
    RebalanceDecision,
    RiskBudgetAllocation,
    StrategyAllocation,
    StrategySnapshot,
)
from .allocator import DynamicAllocator, RebalanceEngine
from .constraints import ConstraintEnforcer, ConstraintValidator
from .optimizer import PortfolioOptimizer


class PortfolioConstructionService:
    """
    Main service for portfolio construction.

    Orchestrates:
    - Strategy snapshot collection
    - Optimization execution
    - Constraint enforcement
    - Allocation generation
    - Rebalance computation
    """

    def __init__(
        self,
        allocator: Optional[DynamicAllocator] = None,
        rebalance_engine: Optional[RebalanceEngine] = None,
        enforcer: Optional[ConstraintEnforcer] = None,
        validator: Optional[ConstraintValidator] = None,
    ):
        self.allocator = allocator or DynamicAllocator()
        self.rebalance_engine = rebalance_engine or RebalanceEngine()
        self.enforcer = enforcer or ConstraintEnforcer()
        self.validator = validator or ConstraintValidator()

    def build(
        self,
        portfolio_id: str,
        capital: float,
        snapshots: Dict[str, StrategySnapshot],
        constraints: Optional[PortfolioConstraints] = None,
        method: OptimizationMethod = OptimizationMethod.MEAN_VARIANCE,
        config: Optional[PortfolioConfig] = None,
    ) -> Portfolio:
        """
        Build a portfolio from strategy snapshots.

        Args:
            portfolio_id: Unique portfolio identifier
            capital: Total capital to allocate
            snapshots: Strategy performance snapshots keyed by strategy_id
            constraints: Portfolio-level constraints
            method: Optimization method
            config: Additional portfolio configuration

        Returns:
            Constructed Portfolio object
        """
        cfg = config or PortfolioConfig(portfolio_id=portfolio_id, capital=capital)

        # Run allocation
        result = self.allocator.allocate(
            portfolio_id=portfolio_id,
            capital=capital,
            snapshots=snapshots,
            constraints=constraints,
            method=method,
            risk_free_rate=cfg.risk_free_rate,
            cash_weight=cfg.min_cash_weight,
            min_cash_weight=cfg.min_cash_weight,
        )

        # Build target weights dict
        target_weights = {
            sid: alloc.target_weight
            for sid, alloc in result.allocations.items()
        }

        # Build current weights dict
        current_weights = {
            sid: snap.current_weight
            for sid, snap in snapshots.items()
        }

        # Compute rebalance decisions
        rebalance_decisions = self.rebalance_engine.compute_decisions(
            current_weights=current_weights,
            target_weights=target_weights,
            capital=capital,
            current_allocations=result.allocations,
        )

        # Determine if rebalance is needed
        rebalance_needed = any(
            d.action.value not in ("hold",) for d in rebalance_decisions
        )

        # Build risk budget dict
        risk_budget = {
            sid: rb.percentage_of_total
            for sid, rb in result.risk_budget_allocations.items()
        }

        return Portfolio(
            portfolio_id=portfolio_id,
            capital=capital,
            strategy_allocations=list(result.allocations.values()),
            target_weights=target_weights,
            current_weights=current_weights,
            cash_weight=result.cash_weight,
            expected_return=result.expected_return,
            expected_volatility=result.expected_volatility,
            expected_sharpe=result.expected_sharpe,
            risk_budget=risk_budget,
            constraints=constraints,
            optimization_method=method,
        )

    def build_multi(
        self,
        portfolio_id: str,
        capital: float,
        strategies_data: List[Dict],
        constraints: Optional[PortfolioConstraints] = None,
        method: OptimizationMethod = OptimizationMethod.MEAN_VARIANCE,
        config: Optional[PortfolioConfig] = None,
    ) -> Portfolio:
        """
        Build a portfolio from raw strategy data dicts.

        Args:
            portfolio_id: Portfolio identifier
            capital: Total capital
            strategies_data: List of strategy performance dicts
            constraints: Portfolio constraints
            method: Optimization method
            config: Portfolio configuration

        Returns:
            Constructed Portfolio
        """
        snapshots = {}
        for data in strategies_data:
            sid = data["strategy_id"]
            snapshots[sid] = StrategySnapshot(
                strategy_id=sid,
                name=data.get("name", sid),
                expected_return=data.get("expected_return", 0.0),
                expected_volatility=data.get("expected_volatility", 0.15),
                sharpe_ratio=data.get("sharpe_ratio", 0.0),
                max_drawdown=data.get("max_drawdown", 0.0),
                recent_alpha=data.get("recent_alpha", 0.0),
                recent_returns=data.get("recent_returns", []),
                win_rate=data.get("win_rate", 0.5),
                sortino_ratio=data.get("sortino_ratio", 0.0),
                calmar_ratio=data.get("calmar_ratio", 0.0),
                current_weight=data.get("current_weight", 0.0),
                factor_exposures=data.get("factor_exposures", {}),
                sector_exposures=data.get("sector_exposures", {}),
                correlation_to_portfolio=data.get("correlation_to_portfolio", 0.3),
                tracking_error=data.get("tracking_error", 0.0),
            )

        return self.build(
            portfolio_id=portfolio_id,
            capital=capital,
            snapshots=snapshots,
            constraints=constraints,
            method=method,
            config=config,
        )

    def rebalance(
        self,
        portfolio: Portfolio,
        new_snapshots: Optional[Dict[str, StrategySnapshot]] = None,
        constraints: Optional[PortfolioConstraints] = None,
        method: Optional[OptimizationMethod] = None,
    ) -> tuple[Portfolio, List[RebalanceDecision]]:
        """
        Rebalance an existing portfolio with new data.

        Args:
            portfolio: Existing portfolio to rebalance
            new_snapshots: Updated strategy snapshots
            constraints: Updated constraints (uses existing if None)
            method: Updated optimization method (uses existing if None)

        Returns:
            Tuple of (updated Portfolio, list of RebalanceDecision)
        """
        # Update current weights from portfolio
        if new_snapshots is None:
            new_snapshots = {}

        # Merge current portfolio weights into snapshots
        for sid, alloc in enumerate(portfolio.strategy_allocations):
            sid_key = alloc.strategy_id
            if sid_key not in new_snapshots:
                new_snapshots[sid_key] = StrategySnapshot(
                    strategy_id=sid_key,
                    name=alloc.strategy_name,
                    current_weight=alloc.current_weight,
                )
            else:
                new_snapshots[sid_key].current_weight = alloc.current_weight

        method = method or portfolio.optimization_method or OptimizationMethod.MEAN_VARIANCE
        constraints = constraints or portfolio.constraints

        # Build new portfolio
        new_portfolio = self.build(
            portfolio_id=portfolio.portfolio_id,
            capital=portfolio.capital,
            snapshots=new_snapshots,
            constraints=constraints,
            method=method,
        )

        # Compute rebalance decisions
        rebalance_decisions = self.rebalance_engine.compute_decisions(
            current_weights=portfolio.target_weights,
            target_weights=new_portfolio.target_weights,
            capital=portfolio.capital,
        )

        return new_portfolio, rebalance_decisions

    def get_allocation(
        self,
        portfolio: Portfolio,
        strategy_id: str,
    ) -> Optional[StrategyAllocation]:
        """Get allocation for a specific strategy in the portfolio."""
        for alloc in portfolio.strategy_allocations:
            if alloc.strategy_id == strategy_id:
                return alloc
        return None

    def get_risk_budget(
        self,
        portfolio: Portfolio,
        strategy_id: str,
    ) -> Optional[float]:
        """Get risk budget for a specific strategy."""
        return portfolio.risk_budget.get(strategy_id)
