"""Capital Allocator — core allocation logic implementing the objective function.

Maximizes: risk-adjusted, capacity-aware, stress-resilient capital efficiency.
Subject to: Capital, Risk, Capacity, Liquidity, Concentration, Stress, Survival constraints.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class AllocatorMode(str, Enum):
    """Capital allocator operating mode."""
    STANDARD = "STANDARD"
    CONSERVATIVE = "CONSERVATIVE"
    AGGRESSIVE = "AGGRESSIVE"
    RISK_PARITY = "RISK_PARITY"
    MAX_DIVERSIFICATION = "MAX_DIVERSIFICATION"


@dataclass
class AllocationTarget:
    """Target allocation for a single strategy."""
    strategy_id: str
    current_capital: float = 0.0
    target_capital: float = 0.0
    weight: float = 0.0
    alpha_score: float = 0.0
    risk_score: float = 0.0
    capacity_score: float = 0.0
    liquidity_score: float = 0.0
    impact_score: float = 0.0
    stress_score: float = 0.0
    survival_score: float = 0.0
    marginal_alpha: float = 0.0
    marginal_risk: float = 0.0
    marginal_cost: float = 0.0
    risk_adjusted_mce: float = 0.0

    @property
    def capital_delta(self) -> float:
        return self.target_capital - self.current_capital


@dataclass
class AllocationPlan:
    """Complete capital allocation plan across all strategies."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_capital: float = 0.0
    reserved: float = 0.0
    buffered: float = 0.0
    deployable: float = 0.0
    targets: List[AllocationTarget] = field(default_factory=list)
    total_allocated: float = 0.0
    remaining_capital: float = 0.0
    objective_value: float = 0.0
    mode: AllocatorMode = AllocatorMode.STANDARD
    iterations: int = 0
    status: str = "PENDING"

    @property
    def allocation_ratio(self) -> float:
        if self.deployable <= 0:
            return 0.0
        return self.total_allocated / self.deployable


class CapitalAllocator:
    """Core capital allocation engine.

    Solves: max Σ(w_i * utility_i)
    subject to: Σw_i ≤ deployable_capital, all constraints.

    Utility_i = alpha_i - λ₁·risk_i - λ₂·cost_i - λ₃·impact_i
                - λ₄·liquidity_i - λ₅·stress_i - λ₆·capacity_i
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._mode = AllocatorMode.STANDARD
        self._reserve_ratio = self._config.get("reserve_ratio", 0.10)
        self._buffer_ratio = self._config.get("buffer_ratio", 0.05)
        self._max_iterations = self._config.get("max_iterations", 100)
        self._convergence_tol = self._config.get("convergence_tol", 1e-6)

        # Objective weights
        self._alpha_weight = self._config.get("alpha_weight", 1.0)
        self._risk_weight = self._config.get("risk_weight", 0.8)
        self._cost_weight = self._config.get("cost_weight", 0.6)
        self._impact_weight = self._config.get("impact_weight", 0.5)
        self._liquidity_weight = self._config.get("liquidity_weight", 0.4)
        self._stress_weight = self._config.get("stress_weight", 0.3)
        self._capacity_weight = self._config.get("capacity_weight", 0.5)

    @property
    def mode(self) -> AllocatorMode:
        return self._mode

    def set_mode(self, mode: AllocatorMode) -> None:
        """Set allocator operating mode with weight adjustments."""
        self._mode = mode
        self._adjust_mode_weights()

    def _adjust_mode_weights(self) -> None:
        """Adjust objective weights based on operating mode."""
        if self._mode == AllocatorMode.CONSERVATIVE:
            self._risk_weight *= 1.5
            self._stress_weight *= 1.5
            self._alpha_weight *= 0.7
        elif self._mode == AllocatorMode.AGGRESSIVE:
            self._alpha_weight *= 1.5
            self._risk_weight *= 0.5
            self._stress_weight *= 0.5
        elif self._mode == AllocatorMode.RISK_PARITY:
            self._alpha_weight = 0.3
            self._risk_weight = 1.5
            self._capacity_weight = 0.3
        elif self._mode == AllocatorMode.MAX_DIVERSIFICATION:
            self._alpha_weight *= 1.2
            self._risk_weight *= 1.2

    def compute_utility(self, target: AllocationTarget) -> float:
        """Compute the allocation utility for a target.

        Utility = Alpha - λ₁·(1-Risk) - λ₂·Cost - λ₃·(1-Impact)
                  - λ₄·(1-Liquidity) - λ₅·(1-Stress) - λ₆·(1-Capacity)

        Higher is better.
        """
        utility = (
            self._alpha_weight * target.alpha_score
            - self._risk_weight * (1.0 - target.risk_score)
            - self._cost_weight * target.marginal_cost
            - self._impact_weight * (1.0 - target.impact_score)
            - self._liquidity_weight * (1.0 - target.liquidity_score)
            - self._stress_weight * (1.0 - target.stress_score)
            - self._capacity_weight * (1.0 - target.capacity_score)
        )
        return utility

    def allocate(self, total_capital: float,
                 candidates: List[AllocationTarget],
                 existing_allocations: Optional[Dict[str, float]] = None,
                 constraints_override: Optional[Dict[str, Any]] = None
                 ) -> AllocationPlan:
        """Execute the allocation across all candidate strategies.

        Uses marginal utility to iteratively allocate capital
        to the strategy with highest marginal utility per unit capital.
        """
        existing = existing_allocations or {}

        reserve = total_capital * self._reserve_ratio
        buffer = total_capital * self._buffer_ratio
        deployable = total_capital - reserve - buffer

        if deployable <= 0 or not candidates:
            return AllocationPlan(
                total_capital=total_capital,
                reserved=reserve,
                buffered=buffer,
                deployable=deployable,
                status="NO_CAPITAL",
            )

        # Initialize from existing or zero
        for t in candidates:
            t.current_capital = existing.get(t.strategy_id, 0.0)
            t.target_capital = t.current_capital

        remaining = deployable - sum(t.current_capital for t in candidates)
        if remaining < 0:
            remaining = 0

        # Iterative allocation
        plan = AllocationPlan(
            total_capital=total_capital,
            reserved=reserve,
            buffered=buffer,
            deployable=deployable,
            targets=list(candidates),
            status="ALLOCATING",
        )

        for iteration in range(self._max_iterations):
            if remaining < self._convergence_tol:
                break

            # Compute marginal utility for each strategy
            best_utility = float("-inf")
            best_idx = -1

            for i, t in enumerate(candidates):
                # Simulate adding 1 unit
                delta = min(remaining * 0.01, remaining)
                if delta <= 0:
                    continue
                marginal_utility = t.marginal_alpha / max(0.001, t.marginal_risk + t.marginal_cost)
                if marginal_utility > best_utility:
                    best_utility = marginal_utility
                    best_idx = i

            if best_idx < 0:
                break

            # Allocate to best strategy
            increment = min(remaining * 0.05, remaining)
            candidates[best_idx].target_capital += increment
            remaining -= increment

        # Finalize
        plan.total_allocated = sum(t.target_capital for t in candidates)
        plan.remaining_capital = deployable - plan.total_allocated
        plan.iterations = min(iteration + 1, self._max_iterations)
        plan.status = "COMPLETE"

        # Compute weights
        if plan.total_allocated > 0:
            for t in candidates:
                t.weight = t.target_capital / total_capital

        # Compute objective value
        plan.objective_value = sum(self.compute_utility(t) * t.weight for t in candidates)

        return plan

    def marginal_allocation(self, incremental_capital: float,
                            candidates: List[AllocationTarget]) -> Dict[str, float]:
        """Determine where incremental capital should go.

        Allocates to the strategy with highest risk-adjusted MCE first.
        """
        if incremental_capital <= 0:
            return {}

        sorted_candidates = sorted(
            candidates,
            key=lambda t: t.risk_adjusted_mce,
            reverse=True,
        )

        result = {}
        remaining = incremental_capital

        for candidate in sorted_candidates:
            if remaining <= 0:
                break
            # Allocate proportionally to MCE
            total_mce = sum(
                max(0, c.risk_adjusted_mce) for c in sorted_candidates
            )
            if total_mce > 0:
                share = remaining * (max(0, candidate.risk_adjusted_mce) / total_mce)
            else:
                share = remaining / len(sorted_candidates)

            result[candidate.strategy_id] = share
            remaining -= share

        return result
