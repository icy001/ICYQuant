"""
Reallocation Decision — Dynamic capital reallocation between strategies.

Triggered by:
    Performance, Risk, Capacity, Correlation changes.

Flow:
    Current Allocation → Evaluate Need → Reallocation Plan → Execute
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ReallocationTrigger(str, Enum):
    PERFORMANCE_DRIFT = "performance_drift"
    RISK_DRIFT = "risk_drift"
    CAPACITY_CHANGE = "capacity_change"
    CORRELATION_BREAKDOWN = "correlation_breakdown"
    DRAWDOWN_EXCEEDED = "drawdown_exceeded"
    REGIME_CHANGE = "regime_change"
    CAPITAL_INFLOW = "capital_inflow"
    CAPITAL_OUTFLOW = "capital_outflow"
    MANUAL = "manual"


@dataclass
class StrategyReallocation:
    """A single strategy's reallocation instruction."""

    strategy_id: str = ""
    source_capital: float = 0.0   # current
    target_capital: float = 0.0   # proposed
    delta: float = 0.0            # target - source
    source_weight: float = 0.0
    target_weight: float = 0.0
    reason: str = ""


@dataclass
class ReallocationPlan:
    """A plan to redistribute capital across strategies."""

    plan_id: str = field(default_factory=lambda: f"RP-{uuid.uuid4().hex[:8]}")
    trigger: ReallocationTrigger = ReallocationTrigger.PERFORMANCE_DRIFT
    trigger_detail: str = ""

    total_capital: float = 0.0
    reallocations: List[StrategyReallocation] = field(default_factory=list)

    expected_return_improvement: float = 0.0
    expected_risk_improvement: float = 0.0
    estimated_cost: float = 0.0
    estimated_net_benefit: float = 0.0

    urgency: str = "LOW"  # LOW, MEDIUM, HIGH, IMMEDIATE

    created_at: str = ""

    @property
    def total_turnover(self) -> float:
        return sum(abs(r.delta) for r in self.reallocations)

    @property
    def turnover_pct(self) -> float:
        return self.total_turnover / max(self.total_capital, 1.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "trigger": self.trigger.value,
            "total_capital": self.total_capital,
            "reallocation_count": len(self.reallocations),
            "total_turnover": self.total_turnover,
            "turnover_pct": self.turnover_pct,
            "expected_return_improvement": self.expected_return_improvement,
            "expected_risk_improvement": self.expected_risk_improvement,
            "estimated_cost": self.estimated_cost,
            "estimated_net_benefit": self.estimated_net_benefit,
            "urgency": self.urgency,
        }

    def increases(self) -> List[StrategyReallocation]:
        return [r for r in self.reallocations if r.delta > 0]

    def decreases(self) -> List[StrategyReallocation]:
        return [r for r in self.reallocations if r.delta < 0]


class ReallocationDecisionEngine:
    """Generates and manages capital reallocation plans."""

    def __init__(self):
        self._plans: List[ReallocationPlan] = []
        self._history: List[ReallocationPlan] = []

    def evaluate(
        self,
        current_allocations: Dict[str, Tuple[float, float]],  # (capital, weight)
        target_allocations: Dict[str, Tuple[float, float]],
        trigger: ReallocationTrigger = ReallocationTrigger.PERFORMANCE_DRIFT,
    ) -> ReallocationPlan:
        """Create a reallocation plan from current to target allocations."""
        plan = ReallocationPlan(
            trigger=trigger,
        )

        total_capital = sum(c for c, _ in current_allocations.values())
        plan.total_capital = total_capital

        all_strategies = set(current_allocations.keys()) | set(target_allocations.keys())
        for sid in sorted(all_strategies):
            src_cap, src_w = current_allocations.get(sid, (0.0, 0.0))
            tgt_cap, tgt_w = target_allocations.get(sid, (0.0, 0.0))
            delta = tgt_cap - src_cap
            if abs(delta) > 1e-6:
                plan.reallocations.append(StrategyReallocation(
                    strategy_id=sid,
                    source_capital=src_cap,
                    target_capital=tgt_cap,
                    delta=delta,
                    source_weight=src_w,
                    target_weight=tgt_w,
                    reason=f"Reallocation from {src_cap:,.0f} to {tgt_cap:,.0f}",
                ))

        # Cost estimate (5 bps of turnover)
        plan.estimated_cost = plan.total_turnover * 0.0005

        # Urgency assessment
        if plan.turnover_pct > 0.25:
            plan.urgency = "IMMEDIATE"
        elif plan.turnover_pct > 0.10:
            plan.urgency = "HIGH"
        elif plan.turnover_pct > 0.03:
            plan.urgency = "MEDIUM"
        else:
            plan.urgency = "LOW"

        plan.estimated_net_benefit = plan.expected_return_improvement - plan.estimated_cost

        self._plans.append(plan)
        return plan

    def should_reallocate(self, plan: ReallocationPlan, min_net_benefit: float = 0.0) -> bool:
        """Determine if reallocation is worth executing."""
        if not plan.reallocations:
            return False
        if plan.estimated_cost > abs(plan.expected_return_improvement) * 2:
            return False
        if plan.estimated_net_benefit < min_net_benefit:
            return False
        return True

    def pending_plans(self) -> List[ReallocationPlan]:
        return list(self._plans)

    def archive(self, plan: ReallocationPlan) -> None:
        if plan in self._plans:
            self._plans.remove(plan)
        self._history.append(plan)

    def summary(self) -> Dict[str, Any]:
        return {
            "pending_plans": len(self._plans),
            "historical_plans": len(self._history),
            "total_historical_turnover": sum(p.total_turnover for p in self._history),
        }
