"""
Allocation Constraints — Hard/soft constraints governing capital distribution.

Constraint categories:
    Capital Limit, Risk Limit, Leverage Limit, Liquidity Limit,
    Strategy Capacity, Concentration Limit, Drawdown Limit, Autonomy Limit.

Optimal Allocation = Objective + Constraints (binding feasibility region).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple


class ConstraintType(str, Enum):
    """Constraint category."""
    HARD = "hard"           # Must be satisfied
    SOFT = "soft"           # Penalized but not enforced strictly
    ABSOLUTE = "absolute"   # Cannot be violated under any condition


class ConstraintBinding(str, Enum):
    """Whether a constraint is currently binding."""
    BINDING = "binding"         # Currently limiting the solution
    SLACK = "slack"             # Not currently limiting
    MARGINAL = "marginal"       # At the boundary
    VIOLATED = "violated"       # Currently violated


@dataclass
class AllocationConstraint:
    """A single allocation constraint with metadata and validation logic."""

    constraint_id: str = field(default_factory=lambda: f"AC-{uuid.uuid4().hex[:8]}")
    name: str = ""
    constraint_type: ConstraintType = ConstraintType.HARD
    field: str = ""                 # e.g. "total_capital", "risk", "leverage"
    operator: str = "le"            # le, ge, eq, range
    limit: float = 0.0
    limit_upper: Optional[float] = None  # for range operator
    priority: int = 50              # lower = higher priority (0 = absolute)
    penalty_weight: float = 1.0     # for soft constraints
    binding: ConstraintBinding = ConstraintBinding.SLACK

    def check(self, value: float) -> Tuple[bool, float]:
        """Check if a value satisfies this constraint.

        Returns:
            (satisfied, violation_amount) — positive violation means over limit.
        """
        if self.operator == "le":
            violation = value - self.limit
            return violation <= 0, violation
        elif self.operator == "ge":
            violation = self.limit - value
            return violation <= 0, -violation
        elif self.operator == "eq":
            violation = abs(value - self.limit)
            return violation < 1e-9, violation
        elif self.operator == "range":
            lo, hi = self.limit, (self.limit_upper or float("inf"))
            if value < lo:
                return False, lo - value
            if value > hi:
                return False, value - hi
            return True, 0.0
        return True, 0.0

    def penalty(self, value: float) -> float:
        """Compute penalty for soft constraint violation."""
        satisfied, violation = self.check(value)
        if satisfied:
            return 0.0
        return self.penalty_weight * max(0.0, violation) ** 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "name": self.name,
            "type": self.constraint_type.value,
            "field": self.field,
            "operator": self.operator,
            "limit": self.limit,
            "limit_upper": self.limit_upper,
            "priority": self.priority,
            "binding": self.binding.value,
        }


@dataclass
class ConstraintSet:
    """A named collection of constraints applied to an allocation problem."""

    set_id: str = field(default_factory=lambda: f"CS-{uuid.uuid4().hex[:8]}")
    name: str = ""
    constraints: List[AllocationConstraint] = field(default_factory=list)

    def add(self, c: AllocationConstraint) -> None:
        self.constraints.append(c)

    def get_hard(self) -> List[AllocationConstraint]:
        return [c for c in self.constraints if c.constraint_type == ConstraintType.HARD]

    def get_soft(self) -> List[AllocationConstraint]:
        return [c for c in self.constraints if c.constraint_type == ConstraintType.SOFT]

    def get_by_field(self, field: str) -> List[AllocationConstraint]:
        return [c for c in self.constraints if c.field == field]

    def check_all(self, values: Dict[str, float]) -> Tuple[bool, List[str]]:
        """Check hard constraints against a values dict. Returns (valid, violations)."""
        violations: List[str] = []
        for c in self.get_hard():
            if c.field not in values:
                continue
            ok, v = c.check(values[c.field])
            c.binding = ConstraintBinding.BINDING if abs(v) < 1e-6 else (
                ConstraintBinding.VIOLATED if not ok else ConstraintBinding.SLACK
            )
            if not ok:
                violations.append(f"{c.name}: {c.field}={values[c.field]} violates {c.operator} {c.limit}")
        return len(violations) == 0, violations

    def total_penalty(self, values: Dict[str, float]) -> float:
        """Sum of soft-constraint penalties."""
        return sum(c.penalty(values.get(c.field, 0.0)) for c in self.get_soft())


class AllocationConstraintBuilder:
    """Fluent builder for institutional allocation constraints."""

    def __init__(self):
        self._constraint_set = ConstraintSet(name="Default")

    def with_name(self, name: str) -> "AllocationConstraintBuilder":
        self._constraint_set.name = name
        return self

    def capital_limit(self, limit: float, constraint_type: ConstraintType = ConstraintType.HARD) -> "AllocationConstraintBuilder":
        self._constraint_set.add(AllocationConstraint(
            name="CapitalLimit", field="total_capital", operator="le",
            limit=limit, constraint_type=constraint_type, priority=0,
        ))
        return self

    def risk_limit(self, limit: float, constraint_type: ConstraintType = ConstraintType.HARD) -> "AllocationConstraintBuilder":
        self._constraint_set.add(AllocationConstraint(
            name="RiskLimit", field="risk", operator="le",
            limit=limit, constraint_type=constraint_type, priority=1,
        ))
        return self

    def leverage_limit(self, limit: float, constraint_type: ConstraintType = ConstraintType.HARD) -> "AllocationConstraintBuilder":
        self._constraint_set.add(AllocationConstraint(
            name="LeverageLimit", field="leverage", operator="le",
            limit=limit, constraint_type=constraint_type, priority=2,
        ))
        return self

    def liquidity_limit(self, limit: float, constraint_type: ConstraintType = ConstraintType.SOFT) -> "AllocationConstraintBuilder":
        self._constraint_set.add(AllocationConstraint(
            name="LiquidityLimit", field="liquidity_usage", operator="le",
            limit=limit, constraint_type=constraint_type, priority=10, penalty_weight=5.0,
        ))
        return self

    def strategy_capacity_limit(self, limit: float) -> "AllocationConstraintBuilder":
        self._constraint_set.add(AllocationConstraint(
            name="StrategyCapacity", field="strategy_capital", operator="le",
            limit=limit, constraint_type=ConstraintType.HARD, priority=3,
        ))
        return self

    def concentration_limit(self, limit: float, constraint_type: ConstraintType = ConstraintType.HARD) -> "AllocationConstraintBuilder":
        self._constraint_set.add(AllocationConstraint(
            name="ConcentrationLimit", field="max_single_weight", operator="le",
            limit=limit, constraint_type=constraint_type, priority=4,
        ))
        return self

    def drawdown_limit(self, limit: float, constraint_type: ConstraintType = ConstraintType.HARD) -> "AllocationConstraintBuilder":
        self._constraint_set.add(AllocationConstraint(
            name="DrawdownLimit", field="drawdown", operator="le",
            limit=limit, constraint_type=constraint_type, priority=5,
        ))
        return self

    def turnover_limit(self, limit: float, constraint_type: ConstraintType = ConstraintType.SOFT) -> "AllocationConstraintBuilder":
        self._constraint_set.add(AllocationConstraint(
            name="TurnoverLimit", field="turnover", operator="le",
            limit=limit, constraint_type=constraint_type, priority=15, penalty_weight=2.0,
        ))
        return self

    def autonomy_limit(self, limit: float) -> "AllocationConstraintBuilder":
        self._constraint_set.add(AllocationConstraint(
            name="AutonomyLimit", field="autonomy_action_size", operator="le",
            limit=limit, constraint_type=ConstraintType.ABSOLUTE, priority=0,
        ))
        return self

    def add_custom(self, name: str, field: str, operator: str, limit: float,
                   constraint_type: ConstraintType = ConstraintType.SOFT,
                   priority: int = 20, penalty_weight: float = 1.0) -> "AllocationConstraintBuilder":
        self._constraint_set.add(AllocationConstraint(
            name=name, field=field, operator=operator, limit=limit,
            constraint_type=constraint_type, priority=priority, penalty_weight=penalty_weight,
        ))
        return self

    def build(self) -> ConstraintSet:
        return self._constraint_set


def build_institutional_constraints(
    total_capital: float,
    max_risk: float = 0.20,
    max_leverage: float = 2.0,
    max_concentration: float = 0.25,
    max_drawdown: float = 0.15,
    autonomy_action_limit: float = 0.0,
) -> ConstraintSet:
    """Build standard institutional constraint set."""
    builder = AllocationConstraintBuilder().with_name("Institutional")
    builder.capital_limit(total_capital)
    builder.risk_limit(max_risk)
    builder.leverage_limit(max_leverage)
    builder.concentration_limit(max_concentration)
    builder.drawdown_limit(max_drawdown)
    if autonomy_action_limit > 0:
        builder.autonomy_limit(autonomy_action_limit)
    return builder.build()
