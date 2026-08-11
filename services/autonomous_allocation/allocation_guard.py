"""Allocation Guard — highest-level safety gate for autonomous allocation.

Wraps ALL constraint and guard checks into a single gate:
Capital, Risk, Capacity, Liquidity, Impact, Stress, Survival.

Any autonomous allocation MUST pass this guard before execution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AllocationGuardResult(str, Enum):
    """Allocation guard result."""
    APPROVED = "APPROVED"
    APPROVED_WITH_CONDITIONS = "APPROVED_WITH_CONDITIONS"
    RESIZE_REQUIRED = "RESIZE_REQUIRED"
    DEFERRED = "DEFERRED"
    REJECTED = "REJECTED"
    EMERGENCY_ONLY = "EMERGENCY_ONLY"


@dataclass
class GuardCondition:
    """A condition imposed on an approved allocation."""
    condition_type: str
    description: str
    max_capital: Optional[float] = None
    max_participation: Optional[float] = None
    review_required: bool = False


@dataclass
class AllocationGuardDecision:
    """Complete allocation guard decision."""
    strategy_id: str
    decision_id: str = ""
    result: AllocationGuardResult = AllocationGuardResult.APPROVED
    capital_limit: float = 0.0
    risk_limit: float = 0.0
    conditions: List[GuardCondition] = field(default_factory=list)
    reject_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class AllocationGuard:
    """Ultimate safety gate for autonomous allocation.

    Integrates:
    - Capital constraint
    - Risk constraint
    - Capacity constraint
    - Liquidity constraint
    - Concentration constraint
    - Stress constraint
    - Survival constraint

    Principle: even if expected return is higher, if any
    critical constraint fails → REJECT.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._max_allocation_ratio = self._config.get("max_allocation_ratio", 0.95)
        self._min_survival = self._config.get("min_survival", 0.70)
        self._max_concentration = self._config.get("max_concentration", 0.35)
        self._min_liquidity = self._config.get("min_liquidity", 0.15)
        self._max_stress_dd = self._config.get("max_stress_dd", 0.25)

    def guard(self, strategy_id: str, decision_id: str,
              total_capital: float = 0.0,
              deployed_capital: float = 0.0,
              target_capital: float = 0.0,
              risk_budget: float = 0.0,
              portfolio_risk: float = 0.0,
              capacity_pct: float = 0.0,
              liquidity_score: float = 0.0,
              survival_score: float = 0.0,
              stress_drawdown: float = 0.0,
              weight: float = 0.0) -> AllocationGuardDecision:
        """Run the complete allocation guard."""

        decision = AllocationGuardDecision(
            strategy_id=strategy_id,
            decision_id=decision_id,
        )

        reject_reasons = []
        warnings = []
        conditions = []

        # Check 1: Capital limit
        if total_capital > 0:
            allocation_ratio = (deployed_capital + target_capital) / total_capital
            if allocation_ratio > self._max_allocation_ratio:
                reject_reasons.append(
                    f"Allocation ratio {allocation_ratio:.2%} > max {self._max_allocation_ratio:.2%}"
                )
                decision.capital_limit = deployed_capital + total_capital * self._max_allocation_ratio - deployed_capital

        # Check 2: Risk budget
        if risk_budget > 0 and portfolio_risk > risk_budget:
            reject_reasons.append(
                f"Portfolio risk {portfolio_risk:.4f} > budget {risk_budget:.4f}"
            )
            decision.risk_limit = risk_budget

        # Check 3: Capacity
        if capacity_pct > 0.95:
            reject_reasons.append(f"Strategy at {capacity_pct:.1%} capacity")
            conditions.append(GuardCondition(
                condition_type="CAPACITY_LIMITED",
                description=f"Near capacity: reduce target",
                max_capital=target_capital * 0.5,
            ))
        elif capacity_pct > 0.85:
            warnings.append(f"Capacity utilization at {capacity_pct:.1%}")

        # Check 4: Liquidity
        if liquidity_score < self._min_liquidity:
            if liquidity_score < 0.10:
                reject_reasons.append(
                    f"Liquidity score {liquidity_score:.2f} critically low"
                )
            else:
                warnings.append(f"Liquidity score {liquidity_score:.2f} below minimum")
                conditions.append(GuardCondition(
                    condition_type="LIQUIDITY_LIMITED",
                    description="Reduce allocation due to low liquidity",
                    max_participation=0.05,
                ))

        # Check 5: Concentration
        if weight > self._max_concentration:
            reject_reasons.append(
                f"Weight {weight:.2%} exceeds max concentration {self._max_concentration:.2%}"
            )
            conditions.append(GuardCondition(
                condition_type="CONCENTRATION_LIMITED",
                description=f"Weight capped at {self._max_concentration:.2%}",
                max_capital=total_capital * self._max_concentration,
            ))

        # Check 6: Stress
        if stress_drawdown > self._max_stress_dd:
            reject_reasons.append(
                f"Stress drawdown {stress_drawdown:.2%} > max {self._max_stress_dd:.2%}"
            )

        # Check 7: Survival (ABSOLUTE)
        if survival_score < self._min_survival:
            reject_reasons.append(
                f"Survival score {survival_score:.3f} < min {self._min_survival:.3f} — ABSOLUTE REJECT"
            )
        elif survival_score < self._min_survival + 0.05:
            warnings.append(f"Survival score {survival_score:.3f} near minimum")

        # Determine result
        decision.reject_reasons = reject_reasons
        decision.warnings = warnings
        decision.conditions = conditions

        if reject_reasons:
            # Check if any are ABSOLUTE
            if any("ABSOLUTE" in r for r in reject_reasons):
                decision.result = AllocationGuardResult.EMERGENCY_ONLY
            else:
                decision.result = AllocationGuardResult.REJECTED
        elif conditions:
            decision.result = AllocationGuardResult.APPROVED_WITH_CONDITIONS
        elif warnings:
            decision.result = AllocationGuardResult.APPROVED
        else:
            decision.result = AllocationGuardResult.APPROVED

        return decision
