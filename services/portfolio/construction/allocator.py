"""
Dynamic Allocator and Rebalance Engine

Converts strategy performance data into portfolio allocations.
Handles:
- Dynamic weight adjustment based on recent performance
- Rebalance decision generation
- Capital allocation computation
- Cash buffer management
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .models import (
    AllocationReason,
    AllocationResult,
    ExposureReport,
    OptimizationMethod,
    OptimizationMetrics,
    OptimizationResult,
    PortfolioConstraints,
    RebalanceAction,
    RebalanceDecision,
    RiskBudgetAllocation,
    StrategyAllocation,
    StrategySnapshot,
)
from .optimizer import (
    MaxSharpeOptimizer,
    MeanVarianceOptimizer,
    MinVarianceOptimizer,
    PortfolioOptimizer,
    RiskParityOptimizer,
)
from .constraints import ConstraintEnforcer, ConstraintValidator


class DynamicAllocator:
    """
    Dynamic allocation engine that converts strategy performance
    into optimal portfolio weights.

    Takes strategy attribution data (alpha, Sharpe, drawdown, etc.)
    and produces target weights through optimization.
    """

    def __init__(
        self,
        optimizer: Optional[PortfolioOptimizer] = None,
        enforcer: Optional[ConstraintEnforcer] = None,
        validator: Optional[ConstraintValidator] = None,
    ):
        self.optimizer = optimizer or MeanVarianceOptimizer()
        self.enforcer = enforcer or ConstraintEnforcer()
        self.validator = validator or ConstraintValidator()
        self._optimizers = {
            OptimizationMethod.MEAN_VARIANCE: MeanVarianceOptimizer(),
            OptimizationMethod.RISK_PARITY: RiskParityOptimizer(),
            OptimizationMethod.MAX_SHARPE: MaxSharpeOptimizer(),
            OptimizationMethod.MIN_VARIANCE: MinVarianceOptimizer(),
        }

    def allocate(
        self,
        portfolio_id: str,
        capital: float,
        snapshots: Dict[str, StrategySnapshot],
        constraints: Optional[PortfolioConstraints] = None,
        method: OptimizationMethod = OptimizationMethod.MEAN_VARIANCE,
        risk_free_rate: float = 0.0,
        cash_weight: float = 0.0,
        min_cash_weight: float = 0.0,
    ) -> AllocationResult:
        """
        Compute optimal strategy allocations.

        Args:
            portfolio_id: Portfolio identifier
            capital: Total capital to allocate
            snapshots: Strategy performance snapshots
            constraints: Portfolio-level constraints
            method: Optimization method to use
            risk_free_rate: Risk-free rate for Sharpe calculation
            cash_weight: Target cash allocation
            min_cash_weight: Minimum cash allocation

        Returns:
            AllocationResult with target weights and metrics
        """
        # Get appropriate optimizer
        opt = self._optimizers.get(method, self.optimizer)

        # Run optimization
        old_weights = {
            sid: snap.current_weight for sid, snap in snapshots.items()
        }

        result: OptimizationResult = opt.optimize(
            snapshots=snapshots,
            constraints=constraints,
            old_weights=old_weights,
            risk_free_rate=risk_free_rate,
        )

        # Reserve cash
        raw_weights = dict(result.weights)
        investable_weight = 1.0 - max(cash_weight, min_cash_weight)
        total_raw = sum(raw_weights.values())

        weights = {}
        if total_raw > 0:
            scale = investable_weight / total_raw
            weights = {sid: w * scale for sid, w in raw_weights.items()}

        # Enforce constraints
        weights = self.enforcer.enforce(weights, snapshots, constraints)

        # Build strategy allocations
        allocations = {}
        for sid, weight in weights.items():
            snap = snapshots.get(sid)
            name = snap.name if snap else sid
            cap = capital * weight

            # Determine reason
            if snap and snap.recent_alpha > 0 and snap.sharpe_ratio > 1.0:
                reason = AllocationReason.DYNAMIC_ADJUSTMENT
            elif weight > (1.0 / max(len(weights), 1)):
                reason = AllocationReason.OPTIMIZATION
            else:
                reason = AllocationReason.RISK_REDUCTION

            constraints_hit = []
            if constraints:
                for sid2, wc in constraints.weight_constraints.items():
                    if sid2 == sid:
                        if weight <= wc.min_weight:
                            constraints_hit.append("min_weight")
                        if weight >= wc.max_weight:
                            constraints_hit.append("max_weight")

            allocations[sid] = StrategyAllocation(
                strategy_id=sid,
                strategy_name=name,
                target_weight=weight,
                current_weight=old_weights.get(sid, 0.0),
                capital_allocated=cap,
                expected_return_contribution=weight * (snap.expected_return if snap else 0),
                risk_contribution=0.0,
                risk_budget_used=0.0,
                reason=reason,
                constraints_hit=constraints_hit,
            )

        # Calculate risk budget allocations
        risk_budgets = self._compute_risk_budgets(weights, snapshots)

        # Calculate exposures
        exposures = None
        if constraints:
            factor_exposures = self.enforcer.calculate_factor_exposures(
                weights, snapshots, constraints.factor_constraints
            )
            sector_exposures = self.enforcer.calculate_sector_exposures(
                weights, snapshots, constraints.sector_constraints
            )
            concentration_warnings = self._check_concentration(weights, snapshots)
            exposures = ExposureReport(
                portfolio_id=portfolio_id,
                factor_exposures=factor_exposures,
                sector_exposures=sector_exposures,
                concentration_warnings=concentration_warnings,
            )

        # Validate
        violations = self.validator.validate(weights, snapshots, constraints)

        # Build metrics
        metrics = result.metrics

        return AllocationResult(
            portfolio_id=portfolio_id,
            allocations=allocations,
            cash_weight=max(cash_weight, min_cash_weight),
            expected_return=metrics.expected_return,
            expected_volatility=metrics.expected_volatility,
            expected_sharpe=metrics.sharpe_ratio,
            optimization_metrics=metrics,
            risk_budget_allocations=risk_budgets,
            exposure_report=exposures,
            constraint_violations=violations,
            method=method,
            timestamp=datetime.utcnow().isoformat(),
        )

    def allocate_equal_weight(
        self,
        portfolio_id: str,
        capital: float,
        snapshots: Dict[str, StrategySnapshot],
        constraints: Optional[PortfolioConstraints] = None,
        cash_weight: float = 0.0,
    ) -> AllocationResult:
        """Compute equal-weight allocation."""
        n = len(snapshots)
        if n == 0:
            return AllocationResult(portfolio_id=portfolio_id)

        investable = 1.0 - max(cash_weight, 0.0)
        weight = investable / n
        weights = {sid: weight for sid in snapshots}

        weights = self.enforcer.enforce(weights, snapshots, constraints)

        allocations = {}
        for sid, w in weights.items():
            snap = snapshots[sid]
            allocations[sid] = StrategyAllocation(
                strategy_id=sid,
                strategy_name=snap.name,
                target_weight=w,
                current_weight=snap.current_weight,
                capital_allocated=capital * w,
                reason=AllocationReason.EQUAL_WEIGHT,
            )

        return AllocationResult(
            portfolio_id=portfolio_id,
            allocations=allocations,
            cash_weight=max(cash_weight, 0.0),
            method=OptimizationMethod.EQUAL_WEIGHT,
            timestamp=datetime.utcnow().isoformat(),
        )

    def _compute_risk_budgets(
        self,
        weights: Dict[str, float],
        snapshots: Dict[str, StrategySnapshot],
    ) -> Dict[str, RiskBudgetAllocation]:
        """Compute risk budget allocations based on weights and volatilities."""
        budgets = {}
        total_risk = 0.0

        for sid, w in weights.items():
            snap = snapshots.get(sid)
            vol = snap.expected_volatility if snap else 0.01
            risk = w * vol
            total_risk += risk

        for sid, w in weights.items():
            snap = snapshots.get(sid)
            vol = snap.expected_volatility if snap else 0.01
            risk = w * vol
            pct = risk / max(total_risk, 1e-12)

            budgets[sid] = RiskBudgetAllocation(
                strategy_id=sid,
                risk_budget=risk,
                risk_used=risk,
                risk_remaining=0.0,
                marginal_risk=vol,
                percentage_of_total=pct,
            )

        return budgets

    def _check_concentration(
        self,
        weights: Dict[str, float],
        snapshots: Dict[str, StrategySnapshot],
    ) -> List[str]:
        """Check for concentration risks."""
        warnings = []

        # Single strategy concentration
        for sid, w in weights.items():
            if w > 0.4:
                warnings.append(f"Strategy {sid} has high concentration: {w:.1%}")

        # Top-2 concentration
        sorted_weights = sorted(weights.values(), reverse=True)
        if len(sorted_weights) >= 2:
            top2 = sorted_weights[0] + sorted_weights[1]
            if top2 > 0.7:
                warnings.append(f"Top 2 strategies account for {top2:.1%} of portfolio")

        return warnings


class RebalanceEngine:
    """
    Rebalance engine that computes rebalance decisions.

    Compares current weights to target weights and generates
    BUY/SELL/HOLD/ADD/REMOVE decisions with capital deltas.
    """

    def __init__(self, threshold: float = 0.02):
        """
        Args:
            threshold: Minimum weight deviation to trigger rebalance (e.g. 0.02 = 2%)
        """
        self.threshold = threshold

    def compute_decisions(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        capital: float,
        current_allocations: Optional[Dict[str, StrategyAllocation]] = None,
    ) -> List[RebalanceDecision]:
        """
        Compute rebalance decisions by comparing current vs target weights.

        Args:
            current_weights: Current portfolio weights
            target_weights: Target portfolio weights
            capital: Total portfolio capital
            current_allocations: Current strategy allocations

        Returns:
            List of RebalanceDecision objects
        """
        decisions = []
        all_strategies = set(current_weights.keys()) | set(target_weights.keys())

        for sid in sorted(all_strategies):
            current = current_weights.get(sid, 0.0)
            target = target_weights.get(sid, 0.0)
            delta = target - current
            capital_delta = capital * delta

            # Determine action
            if abs(delta) < self.threshold and current > 0 and target > 0:
                action = RebalanceAction.HOLD
                reason = "Within threshold"
            elif current == 0 and target > 0:
                action = RebalanceAction.ADD
                reason = f"New allocation: {target:.2%}"
            elif target == 0 and current > 0:
                action = RebalanceAction.REMOVE
                reason = f"Removing strategy (current: {current:.2%})"
            elif delta > 0:
                action = RebalanceAction.BUY
                reason = f"Increase from {current:.2%} to {target:.2%}"
            elif delta < 0:
                action = RebalanceAction.SELL
                reason = f"Reduce from {current:.2%} to {target:.2%}"
            else:
                action = RebalanceAction.HOLD
                reason = "No change"

            decision = RebalanceDecision(
                strategy_id=sid,
                action=action,
                current_weight=current,
                target_weight=target,
                weight_delta=delta,
                capital_delta=capital_delta,
                reason=reason,
            )
            decisions.append(decision)

        return decisions

    def needs_rebalance(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
    ) -> bool:
        """Check if rebalancing is needed based on threshold."""
        decisions = self.compute_decisions(current_weights, target_weights, 1.0)
        for d in decisions:
            if d.action not in (RebalanceAction.HOLD,):
                return True
        return False

    def calculate_turnover(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
    ) -> float:
        """Calculate two-way turnover between current and target weights."""
        all_keys = set(current_weights.keys()) | set(target_weights.keys())
        turnover = 0.0
        for k in all_keys:
            turnover += abs(target_weights.get(k, 0.0) - current_weights.get(k, 0.0))
        return turnover / 2.0

    def generate_orders(
        self,
        decisions: List[RebalanceDecision],
        capital: float,
    ) -> List[Dict]:
        """Convert rebalance decisions to order instructions."""
        orders = []
        for d in decisions:
            if d.action in (RebalanceAction.HOLD,):
                continue

            orders.append({
                "strategy_id": d.strategy_id,
                "action": d.action.value,
                "capital_amount": abs(d.capital_delta),
                "direction": "long",
                "weight_change": d.weight_delta,
                "reason": d.reason,
            })

        return orders
