"""
Risk Budget Engine — manages risk budget lifecycle and distribution.

Acts as the coordination layer between dynamic risk budget allocation
and individual risk constraints (exposure, leverage, concentration).

Workflow:
    Market Regime → Dynamic Budget → Strategy Allocation → Asset Allocation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class BudgetAllocation:
    """A single-layer budget allocation."""
    name: str
    risk_budget: float = 0.0
    capital_weight: float = 0.0
    risk_weight: float = 0.0
    max_exposure: float = 0.0
    min_exposure: float = 0.0
    target_vol: float = 0.15
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskBudgetPlan:
    """Complete risk budget plan with all layers."""
    id: str = field(default_factory=lambda: str(uuid4()))
    total_budget: float = 1.0
    effective_budget: float = 1.0
    strategy_budgets: list[BudgetAllocation] = field(default_factory=list)
    factor_budgets: list[BudgetAllocation] = field(default_factory=list)
    asset_budgets: list[BudgetAllocation] = field(default_factory=list)
    regime: str = "NORMAL"
    unused_budget: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class RiskBudgetEngine:
    """
    Risk budget engine — lifecycle management of risk budgets.

    Capabilities:
        - Top-down budget allocation (total → strategy → factor → asset)
        - Budget utilization tracking
        - Budget rebalancing triggers
        - Unused budget detection
        - Budget breach alerts
    """

    def __init__(self, total_budget: float = 1.0) -> None:
        self._total_budget = total_budget
        self._current_plan: Optional[RiskBudgetPlan] = None
        self._allocation_history: list[RiskBudgetPlan] = []

    async def create_plan(
        self,
        strategies: list[dict],
        regime: str = "NORMAL",
        available_budget: float = 1.0,
    ) -> RiskBudgetPlan:
        """
        Create a multi-layer risk budget plan.

        Args:
            strategies: List of strategy configs [{name, risk_score, ...}]
            regime: Current market regime
            available_budget: Total available risk budget
        """
        plan = RiskBudgetPlan(
            total_budget=self._total_budget,
            effective_budget=available_budget,
            regime=regime,
        )

        # Layer 1: Strategy budget allocation
        total_strategy_score = sum(s.get("risk_score", 1.0) for s in strategies) or len(strategies)
        for s in strategies:
            score = s.get("risk_score", 1.0)
            budget = available_budget * (score / total_strategy_score)
            plan.strategy_budgets.append(BudgetAllocation(
                name=s.get("name", "unknown"),
                risk_budget=budget,
                capital_weight=budget / available_budget if available_budget else 0,
                max_exposure=min(budget * 1.5, 0.30),
                min_exposure=0.0,
            ))

        # Compute unused budget
        used = sum(b.risk_budget for b in plan.strategy_budgets)
        plan.unused_budget = max(0, available_budget - used)

        plan.timestamp = datetime.now()
        self._current_plan = plan
        self._allocation_history.append(plan)

        logger.info(
            "Budget plan created: total=%.2f used=%.2f unused=%.2f strategies=%d",
            plan.effective_budget, used, plan.unused_budget, len(strategies),
        )
        return plan

    async def rebalance(self, current_utilization: dict[str, float]) -> RiskBudgetPlan:
        """
        Rebalance budgets based on current utilization.

        Reallocates unused budget from under-utilized to over-utilized.
        """
        if not self._current_plan:
            return await self.create_plan([{"name": "default", "risk_score": 1.0}])

        plan = self._current_plan
        total_unused = 0.0
        needs_more = []

        for budget in plan.strategy_budgets:
            used = current_utilization.get(budget.name, 0)
            if used < budget.risk_budget * 0.80:
                surplus = budget.risk_budget - used
                total_unused += surplus
                budget.risk_budget = used
            elif used > budget.risk_budget * 0.95:
                needs_more.append(budget)

        # Redistribute unused
        if needs_more and total_unused > 0:
            per_need = total_unused / len(needs_more)
            for b in needs_more:
                b.risk_budget += per_need

        plan.unused_budget = max(0, total_unused - len(needs_more) * (
            total_unused / len(needs_more) if needs_more else 0
        ))
        plan.timestamp = datetime.now()

        logger.info("Rebalanced: unused=%.2f redistributed_to=%d", total_unused, len(needs_more))
        return plan

    async def check_breaches(self) -> list[dict]:
        """Check for budget breaches across all allocations."""
        breaches = []
        if not self._current_plan:
            return breaches

        for budget in self._current_plan.strategy_budgets:
            if budget.risk_budget > budget.max_exposure:
                breaches.append({
                    "type": "exposure_breach",
                    "allocation": budget.name,
                    "budget": budget.risk_budget,
                    "max": budget.max_exposure,
                })
        return breaches

    @property
    def current_plan(self) -> Optional[RiskBudgetPlan]:
        return self._current_plan

    def get_available_budget(self) -> float:
        if self._current_plan:
            return self._current_plan.effective_budget
        return self._total_budget
