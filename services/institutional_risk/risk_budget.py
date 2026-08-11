"""RiskBudget — unified risk budget management.

Defines, allocates, and tracks the total capital risk budget
across strategies and portfolios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class RiskBudgetAllocation:
    """Risk budget allocation to an entity."""

    entity_id: str
    risk_budget: float
    risk_used: float = 0.0
    risk_available: float = 0.0
    utilization_pct: float = 0.0
    efficiency_score: float = 1.0
    status: str = "OK"


@dataclass
class RiskBudgetStatus:
    """Overall risk budget status."""

    total_budget: float = 0.0
    total_used: float = 0.0
    total_available: float = 0.0
    utilization_pct: float = 0.0
    allocations: Dict[str, RiskBudgetAllocation] = field(default_factory=dict)
    status: str = "OK"
    warnings: List[str] = field(default_factory=list)


class RiskBudgetManager:
    """Manages the capital risk budget.

    Usage::

        manager = RiskBudgetManager(total_capital=100_000_000, budget_ratio=0.08)
        manager.allocate("strat_A", 1_500_000)
        manager.allocate("strat_B", 2_000_000)
        status = manager.get_status()
    666
    """

    def __init__(self, total_capital: float, budget_ratio: float = 0.08):
        self._total_capital = total_capital
        self._budget_ratio = budget_ratio
        self._total_budget = total_capital * budget_ratio
        self._allocations: Dict[str, RiskBudgetAllocation] = {}

    @property
    def total_budget(self) -> float:
        return self._total_budget

    @property
    def total_allocated(self) -> float:
        return sum(a.risk_budget for a in self._allocations.values())

    @property
    def total_used(self) -> float:
        return sum(a.risk_used for a in self._allocations.values())

    @property
    def available_to_allocate(self) -> float:
        return self._total_budget - self.total_allocated

    def allocate(self, entity_id: str, risk_budget: float) -> RiskBudgetAllocation:
        """Allocate risk budget to an entity.

        Args:
            entity_id: strategy or portfolio id
            risk_budget: risk budget amount
        """
        if entity_id in self._allocations:
            self._allocations[entity_id].risk_budget = risk_budget
        else:
            self._allocations[entity_id] = RiskBudgetAllocation(
                entity_id=entity_id,
                risk_budget=risk_budget,
                risk_available=risk_budget,
            )
        return self._allocations[entity_id]

    def update_usage(self, entity_id: str, risk_used: float) -> None:
        """Update the risk used by an entity."""
        if entity_id not in self._allocations:
            self.allocate(entity_id, risk_used)
        alloc = self._allocations[entity_id]
        alloc.risk_used = risk_used
        alloc.risk_available = max(0.0, alloc.risk_budget - risk_used)
        alloc.utilization_pct = (risk_used / max(alloc.risk_budget, 1e-9)) * 100

        if alloc.utilization_pct > 100:
            alloc.status = "BREACH"
        elif alloc.utilization_pct > 80:
            alloc.status = "WARNING"
        else:
            alloc.status = "OK"

    def get_status(self) -> RiskBudgetStatus:
        """Get overall risk budget status."""
        total_used = self.total_used
        utilization = (total_used / max(self._total_budget, 1e-9)) * 100

        status = "OK"
        if utilization > 100:
            status = "BREACH"
        elif utilization > 90:
            status = "WARNING"
        elif utilization > 75:
            status = "ELEVATED"

        warnings: List[str] = []
        for sid, alloc in self._allocations.items():
            if alloc.status == "BREACH":
                warnings.append(f"{sid}: Budget breach ({alloc.utilization_pct:.0f}%)")
            elif alloc.status == "WARNING":
                warnings.append(f"{sid}: Near limit ({alloc.utilization_pct:.0f}%)")

        return RiskBudgetStatus(
            total_budget=self._total_budget,
            total_used=total_used,
            total_available=max(0.0, self._total_budget - total_used),
            utilization_pct=utilization,
            allocations=dict(self._allocations),
            status=status,
            warnings=warnings,
        )

    def reallocate(
        self,
        from_entity: str,
        to_entity: str,
        amount: float,
    ) -> None:
        """Move risk budget from one entity to another."""
        if from_entity in self._allocations:
            current = self._allocations[from_entity].risk_budget
            self._allocations[from_entity].risk_budget = max(0.0, current - amount)
        if to_entity not in self._allocations:
            self.allocate(to_entity, amount)
        else:
            self._allocations[to_entity].risk_budget += amount

    def reset(self) -> None:
        """Reset all allocations."""
        self._allocations.clear()
