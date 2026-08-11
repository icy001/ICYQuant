"""Stress Constraint — ensures candidate allocation passes stress tests.

Checks that portfolio drawdown under stress scenarios stays
below maximum acceptable threshold.
"""

from typing import Any, Dict, List

from .allocation_constraint import (
    AllocationConstraint, ConstraintResult, ConstraintStatus, ConstraintType,
)


class StressConstraint(AllocationConstraint):
    """Ensures allocation survives stress scenarios.

    Stress scenarios include:
    - Market crash (-20%)
    - Volatility spike (+100%)
    - Liquidity dry-up (-50%)
    - Correlation spike (+50%)
    """

    def __init__(self, max_stress_drawdown: float = 0.25,
                 max_var: float = 0.10,
                 max_cvar: float = 0.15):
        super().__init__("stress_constraint", ConstraintType.HARD)
        self._max_stress_drawdown = max_stress_drawdown
        self._max_var = max_var
        self._max_cvar = max_cvar
        self._scenarios: List[Dict[str, Any]] = []

    def add_scenario(self, name: str, impact_fn: callable) -> None:
        """Add a custom stress scenario."""
        self._scenarios.append({"name": name, "impact_fn": impact_fn})

    def set_limits(self, max_drawdown: float = None, max_var: float = None,
                   max_cvar: float = None) -> None:
        if max_drawdown is not None:
            self._max_stress_drawdown = max_drawdown
        if max_var is not None:
            self._max_var = max_var
        if max_cvar is not None:
            self._max_cvar = max_cvar

    def check(self, allocation: Dict[str, Any]) -> ConstraintResult:
        stress_drawdown = allocation.get("stress_drawdown", 0.0)
        stress_var = allocation.get("stress_var", 0.0)
        stress_cvar = allocation.get("stress_cvar", 0.0)

        violations = []

        if stress_drawdown > self._max_stress_drawdown:
            violations.append(
                f"Stress drawdown {stress_drawdown:.2%} > max {self._max_stress_drawdown:.2%}"
            )

        if stress_var > self._max_var:
            violations.append(
                f"Stress VaR {stress_var:.2%} > max {self._max_var:.2%}"
            )

        if stress_cvar > self._max_cvar:
            violations.append(
                f"Stress CVaR {stress_cvar:.2%} > max {self._max_cvar:.2%}"
            )

        if violations:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.VIOLATED,
                violation_severity=min(1.0, len(violations) / 3.0),
                message=f"Stress violations: {'; '.join(violations)}",
                details={
                    "stress_drawdown": stress_drawdown,
                    "stress_var": stress_var,
                    "stress_cvar": stress_cvar,
                },
            )

        return ConstraintResult(
            constraint_name=self.name,
            status=ConstraintStatus.SATISFIED,
            value=stress_drawdown,
            limit=self._max_stress_drawdown,
            margin=self._max_stress_drawdown - stress_drawdown,
            message="Stress constraints satisfied",
        )
