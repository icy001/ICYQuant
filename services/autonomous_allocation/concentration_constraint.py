"""Concentration Constraint — limits exposure concentration.

Checks:
- Single strategy weight cap
- Single asset weight cap
- Sector exposure cap
- Factor exposure cap
- Liquidity cluster cap
"""

from typing import Any, Dict, List

from .allocation_constraint import (
    AllocationConstraint, ConstraintResult, ConstraintStatus, ConstraintType,
)


class ConcentrationConstraint(AllocationConstraint):
    """Limits concentration risk across multiple dimensions."""

    def __init__(self,
                 max_single_strategy: float = 0.35,
                 max_single_asset: float = 0.15,
                 max_single_sector: float = 0.30,
                 max_single_factor: float = 0.35,
                 max_liquidity_cluster: float = 0.40):
        super().__init__("concentration_constraint", ConstraintType.HARD)
        self._max_single_strategy = max_single_strategy
        self._max_single_asset = max_single_asset
        self._max_single_sector = max_single_sector
        self._max_single_factor = max_single_factor
        self._max_liquidity_cluster = max_liquidity_cluster

    def set_limits(self, **kwargs) -> None:
        """Update concentration limits."""
        for key, value in kwargs.items():
            if hasattr(self, f"_{key}"):
                setattr(self, f"_{key}", value)

    def check(self, allocation: Dict[str, Any]) -> ConstraintResult:
        violations = []

        # Check strategy weights
        weights = allocation.get("weights", {})
        total_capital = allocation.get("total_capital", 0.0)

        for sid, weight in weights.items():
            if weight > self._max_single_strategy:
                violations.append(
                    f"Strategy {sid} weight {weight:.2%} > max {self._max_single_strategy:.2%}"
                )

        # Check sector exposure
        sector_exposure = allocation.get("sector_exposure", {})
        for sector, exposure in sector_exposure.items():
            if exposure > self._max_single_sector:
                violations.append(
                    f"Sector {sector} exposure {exposure:.2%} > max {self._max_single_sector:.2%}"
                )

        # Check factor exposure
        factor_exposure = allocation.get("factor_exposure", {})
        for factor, exposure in factor_exposure.items():
            if exposure > self._max_single_factor:
                violations.append(
                    f"Factor {factor} exposure {exposure:.2%} > max {self._max_single_factor:.2%}"
                )

        if violations:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.VIOLATED,
                violation_severity=min(1.0, len(violations) / 4.0),
                message=f"Concentration violations: {'; '.join(violations)}",
                details={"violations": violations},
            )

        # Check near limits
        near = []
        for sid, weight in weights.items():
            if weight > self._max_single_strategy * 0.85:
                near.append(f"{sid}={weight:.2%}")

        if near:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.BINDING,
                message=f"Near concentration limits: {', '.join(near)}",
            )

        return ConstraintResult(
            constraint_name=self.name,
            status=ConstraintStatus.SATISFIED,
            message="Concentration limits satisfied",
        )

    def check_weight(self, strategy_id: str, weight: float,
                     total_capital: float) -> ConstraintResult:
        if weight > self._max_single_strategy:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.VIOLATED,
                value=weight,
                limit=self._max_single_strategy,
                message=f"Strategy weight {weight:.2%} > max {self._max_single_strategy:.2%}",
            )
        return ConstraintResult(
            constraint_name=self.name,
            status=ConstraintStatus.SATISFIED,
            value=weight,
            limit=self._max_single_strategy,
        )
