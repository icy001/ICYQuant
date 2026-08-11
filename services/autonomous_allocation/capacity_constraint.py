"""Capacity Constraint — ensures allocation respects strategy capacity limits.

Each strategy has a maximum capital it can absorb without destroying alpha.
"""

from typing import Any, Dict

from .allocation_constraint import (
    AllocationConstraint, ConstraintResult, ConstraintStatus, ConstraintType,
)


class CapacityConstraint(AllocationConstraint):
    """Ensures per-strategy allocation doesn't exceed capacity."""

    def __init__(self, capacities: Dict[str, float] = None,
                 default_capacity: float = float("inf")):
        super().__init__("capacity_constraint", ConstraintType.HARD)
        self._capacities = capacities or {}
        self._default_capacity = default_capacity

    def set_capacity(self, strategy_id: str, capacity: float) -> None:
        self._capacities[strategy_id] = capacity

    def get_capacity(self, strategy_id: str) -> float:
        return self._capacities.get(strategy_id, self._default_capacity)

    def check(self, allocation: Dict[str, Any]) -> ConstraintResult:
        allocations = allocation.get("allocations", {})
        violations = []

        for sid, capital in allocations.items():
            cap = self.get_capacity(sid)
            if capital > cap:
                violations.append(f"{sid}: {capital:,.0f} > {cap:,.0f}")

        if violations:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.VIOLATED,
                violation_severity=min(1.0, len(violations) / max(1, len(allocations))),
                message=f"Capacity violations: {'; '.join(violations)}",
                details={"violations": violations},
            )

        # Check near-capacity
        near = []
        for sid, capital in allocations.items():
            cap = self.get_capacity(sid)
            if cap > 0 and capital > cap * 0.85:
                near.append(sid)

        if near:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.BINDING,
                message=f"Strategies near capacity: {', '.join(near)}",
                details={"near_capacity": near},
            )

        return ConstraintResult(
            constraint_name=self.name,
            status=ConstraintStatus.SATISFIED,
            message="All strategies within capacity limits",
        )

    def check_weight(self, strategy_id: str, weight: float,
                     total_capital: float) -> ConstraintResult:
        capital = weight * total_capital
        cap = self.get_capacity(strategy_id)

        if capital > cap:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.VIOLATED,
                value=capital,
                limit=cap,
                margin=cap - capital,
                message=f"Strategy {strategy_id} capital {capital:,.0f} > capacity {cap:,.0f}",
            )

        if cap > 0 and capital > cap * 0.85:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.BINDING,
                value=capital,
                limit=cap,
                margin=cap - capital,
                message=f"Strategy {strategy_id} near capacity ({capital/cap:.1%})",
            )

        return ConstraintResult(
            constraint_name=self.name,
            status=ConstraintStatus.SATISFIED,
            value=capital,
            limit=cap,
        )
