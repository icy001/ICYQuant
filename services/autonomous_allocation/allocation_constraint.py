"""Allocation Constraint — abstract constraint framework.

Defines the constraint interface and constraint set for
the unified allocation feasible region.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ConstraintType(str, Enum):
    """Type of allocation constraint."""
    HARD = "HARD"  # Must be satisfied
    SOFT = "SOFT"  # Preferred but can be violated with penalty
    ABSOLUTE = "ABSOLUTE"  # Never violated under any circumstances


class ConstraintStatus(str, Enum):
    """Result of constraint checking."""
    SATISFIED = "SATISFIED"
    VIOLATED = "VIOLATED"
    BINDING = "BINDING"  # At the limit
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class ConstraintResult:
    """Result of checking a constraint."""
    constraint_name: str
    status: ConstraintStatus = ConstraintStatus.SATISFIED
    value: float = 0.0
    limit: float = 0.0
    margin: float = 0.0  # distance to limit (positive = within, negative = exceeded)
    violation_severity: float = 0.0  # 0-1
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_satisfied(self) -> bool:
        return self.status == ConstraintStatus.SATISFIED

    @property
    def is_binding(self) -> bool:
        return self.status == ConstraintStatus.BINDING


@dataclass
class ConstraintSetResult:
    """Result of checking all constraints."""
    results: List[ConstraintResult] = field(default_factory=list)
    all_satisfied: bool = True
    hard_violations: List[str] = field(default_factory=list)
    soft_violations: List[str] = field(default_factory=list)
    binding_constraints: List[str] = field(default_factory=list)

    @property
    def violation_count(self) -> int:
        return len(self.hard_violations) + len(self.soft_violations)


class AllocationConstraint:
    """Abstract base class for allocation constraints."""

    def __init__(self, name: str, constraint_type: ConstraintType = ConstraintType.HARD):
        self._name = name
        self._type = constraint_type
        self._enabled = True

    @property
    def name(self) -> str:
        return self._name

    @property
    def constraint_type(self) -> ConstraintType:
        return self._type

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def check(self, allocation: Dict[str, Any]) -> ConstraintResult:
        """Check if allocation satisfies this constraint. Override in subclasses."""
        return ConstraintResult(
            constraint_name=self._name,
            status=ConstraintStatus.SATISFIED,
            message=f"Default check: always satisfied",
        )

    def check_weight(self, strategy_id: str, weight: float,
                     total_capital: float) -> ConstraintResult:
        """Check weight-based constraint."""
        return ConstraintResult(
            constraint_name=self._name,
            status=ConstraintStatus.SATISFIED,
        )


class ConstraintSet:
    """Collection of allocation constraints checked together."""

    def __init__(self):
        self._constraints: List[AllocationConstraint] = []

    def add(self, constraint: AllocationConstraint) -> None:
        """Add a constraint."""
        self._constraints.append(constraint)

    def remove(self, name: str) -> None:
        """Remove a constraint by name."""
        self._constraints = [c for c in self._constraints if c.name != name]

    def check_all(self, allocation: Dict[str, Any]) -> ConstraintSetResult:
        """Check all constraints and aggregate results."""
        results = []
        hard_violations = []
        soft_violations = []
        binding = []

        for constraint in self._constraints:
            if not constraint.is_enabled:
                continue

            result = constraint.check(allocation)
            results.append(result)

            if not result.is_satisfied:
                if constraint.constraint_type == ConstraintType.HARD:
                    hard_violations.append(constraint.name)
                elif constraint.constraint_type == ConstraintType.SOFT:
                    soft_violations.append(constraint.name)

            if result.is_binding:
                binding.append(constraint.name)

        return ConstraintSetResult(
            results=results,
            all_satisfied=len(hard_violations) == 0,
            hard_violations=hard_violations,
            soft_violations=soft_violations,
            binding_constraints=binding,
        )

    def get_constraint(self, name: str) -> Optional[AllocationConstraint]:
        """Get a constraint by name."""
        for c in self._constraints:
            if c.name == name:
                return c
        return None

    @property
    def count(self) -> int:
        return len(self._constraints)

    def describe(self) -> List[str]:
        """Describe all constraints."""
        return [
            f"[{c.constraint_type.value}] {c.name} (enabled={c.is_enabled})"
            for c in self._constraints
        ]
