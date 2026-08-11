"""Capital Constraint — ensures total allocation doesn't exceed deployable capital.

Deployable Capital = Total Capital - Required Reserve - Required Buffer
"""

from typing import Any, Dict, Tuple
from .allocation_constraint import (
    AllocationConstraint, ConstraintResult, ConstraintStatus, ConstraintType,
)


class CapitalConstraint(AllocationConstraint):
    """Ensures allocations respect available capital."""

    def __init__(self, total_capital: float = 0.0,
                 reserve_ratio: float = 0.10,
                 buffer_ratio: float = 0.05,
                 max_deployment: float = 0.95):
        super().__init__("capital_constraint", ConstraintType.HARD)
        self._total_capital = total_capital
        self._reserve_ratio = reserve_ratio
        self._buffer_ratio = buffer_ratio
        self._max_deployment = max_deployment

    @property
    def deployable_capital(self) -> float:
        reserve = self._total_capital * self._reserve_ratio
        buffer = self._total_capital * self._buffer_ratio
        return (self._total_capital - reserve - buffer) * self._max_deployment

    def set_total_capital(self, capital: float) -> None:
        self._total_capital = capital

    def check(self, allocation: Dict[str, Any]) -> ConstraintResult:
        if self._total_capital <= 0:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.ERROR,
                message="Total capital is zero or negative",
            )

        total_allocated = allocation.get("total_allocated", 0.0)
        deployable = self.deployable_capital
        margin = deployable - total_allocated

        if total_allocated > deployable:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.VIOLATED,
                value=total_allocated,
                limit=deployable,
                margin=-margin,
                violation_severity=min(1.0, (total_allocated - deployable) / max(1, deployable)),
                message=f"Total allocation {total_allocated:,.0f} exceeds deployable {deployable:,.0f}",
            )
        elif margin < deployable * 0.01:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.BINDING,
                value=total_allocated,
                limit=deployable,
                margin=margin,
                message=f"Near capital limit: {margin:,.0f} remaining",
            )

        return ConstraintResult(
            constraint_name=self.name,
            status=ConstraintStatus.SATISFIED,
            value=total_allocated,
            limit=deployable,
            margin=margin,
            message="Capital constraint satisfied",
        )

    def check_weight(self, strategy_id: str, weight: float,
                     total_capital: float) -> ConstraintResult:
        """Check a single strategy's weight against available capital."""
        deployable = self.deployable_capital
        capital_requested = weight * total_capital

        if capital_requested > deployable:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.VIOLATED,
                value=capital_requested,
                limit=deployable,
                margin=deployable - capital_requested,
                message=f"Strategy {strategy_id} capital {capital_requested:,.0f} > deployable {deployable:,.0f}",
            )

        return ConstraintResult(
            constraint_name=self.name,
            status=ConstraintStatus.SATISFIED,
            value=capital_requested,
            limit=deployable,
            margin=deployable - capital_requested,
        )
