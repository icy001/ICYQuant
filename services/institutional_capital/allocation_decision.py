"""
Allocation Decision — Specialized capital allocation decisions with optimization metadata.

Extends CapitalDecision with allocation-specific fields:
    target_weight, capacity_utilization, marginal_efficiency, constraint_bindings.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .capital_decision import CapitalDecision, CapitalDecisionType, DecisionStatus


@dataclass
class AllocationDecision(CapitalDecision):
    """A capital allocation decision with optimization metadata."""

    # Allocation specifics
    target_weight: float = 0.0
    current_weight: float = 0.0
    capacity_used: float = 0.0
    capacity_available: float = 0.0
    capacity_utilization: float = 0.0
    marginal_efficiency: float = 0.0

    # Constraint bindings
    binding_constraints: List[str] = field(default_factory=list)
    constraint_slack: Dict[str, float] = field(default_factory=dict)

    # Optimization
    objective_value: float = 0.0
    optimization_method: str = ""
    iterations: int = 0

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "target_weight": self.target_weight,
            "current_weight": self.current_weight,
            "capacity_utilization": self.capacity_utilization,
            "marginal_efficiency": self.marginal_efficiency,
            "binding_constraints": self.binding_constraints,
            "objective_value": self.objective_value,
        })
        return base

    @classmethod
    def from_capital_decision(cls, cd: CapitalDecision) -> "AllocationDecision":
        return cls(
            decision_id=cd.decision_id,
            decision_type=cd.decision_type,
            status=cd.status,
            strategy_id=cd.strategy_id,
            account_id=cd.account_id,
            current_capital=cd.current_capital,
            target_capital=cd.target_capital,
            delta_capital=cd.delta_capital,
            reason=cd.reason,
            priority_score=cd.priority_score,
        )


class AllocationDecisionMaker:
    """Creates allocation decisions informed by optimization results."""

    def __init__(self):
        self._decisions: List[AllocationDecision] = []

    def decide(
        self,
        strategy_id: str,
        current_capital: float,
        target_capital: float,
        current_weight: float = 0.0,
        target_weight: float = 0.0,
        marginal_efficiency: float = 0.0,
        capacity_utilization: float = 0.0,
        binding_constraints: Optional[List[str]] = None,
    ) -> AllocationDecision:
        delta = target_capital - current_capital

        if abs(delta) < 1e-6:
            decision_type = CapitalDecisionType.HOLD
            reason = "No material change required"
        elif delta > 0:
            decision_type = CapitalDecisionType.INCREASE
            reason = f"Increase by {delta:,.0f} based on marginal efficiency {marginal_efficiency:.4f}"
        else:
            decision_type = CapitalDecisionType.REDUCE
            reason = f"Reduce by {abs(delta):,.0f} due to optimization result"

        decision = AllocationDecision(
            decision_type=decision_type,
            strategy_id=strategy_id,
            current_capital=current_capital,
            target_capital=target_capital,
            current_weight=current_weight,
            target_weight=target_weight,
            marginal_efficiency=marginal_efficiency,
            capacity_utilization=capacity_utilization,
            binding_constraints=binding_constraints or [],
            reason=reason,
        )

        self._decisions.append(decision)
        return decision

    def pending(self) -> List[AllocationDecision]:
        return [d for d in self._decisions if d.status == DecisionStatus.PROPOSED]

    def approved(self) -> List[AllocationDecision]:
        return [d for d in self._decisions if d.status == DecisionStatus.APPROVED]

    def summary(self) -> Dict[str, Any]:
        pending = self.pending()
        total_delta = sum(d.delta_capital for d in pending)
        return {
            "pending_decisions": len(pending),
            "total_capital_change": total_delta,
            "increases": sum(1 for d in pending if d.delta_capital > 0),
            "decreases": sum(1 for d in pending if d.delta_capital < 0),
            "holds": sum(1 for d in pending if d.decision_type == CapitalDecisionType.HOLD),
        }
