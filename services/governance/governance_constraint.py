"""
Governance Constraint — abstract base for all constraints.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .decision_context import DecisionContext
from .decision_request import DecisionRequest


@dataclass
class ConstraintResult:
    """Result of a single constraint evaluation."""

    constraint_name: str
    passed: bool
    reason: str = ""
    blocking: bool = False
    review_required: bool = False
    actual_value: Any = None
    limit_value: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def pass_(cls, name: str, **kwargs) -> "ConstraintResult":
        return cls(constraint_name=name, passed=True, **kwargs)

    @classmethod
    def fail(cls, name: str, reason: str, blocking: bool = True,
             actual: Any = None, limit: Any = None, **kwargs) -> "ConstraintResult":
        return cls(
            constraint_name=name,
            passed=False,
            reason=reason,
            blocking=blocking,
            actual_value=actual,
            limit_value=limit,
            **kwargs,
        )

    @classmethod
    def review(cls, name: str, reason: str, **kwargs) -> "ConstraintResult":
        return cls(
            constraint_name=name,
            passed=True,
            reason=reason,
            review_required=True,
            **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_name": self.constraint_name,
            "passed": self.passed,
            "reason": self.reason,
            "blocking": self.blocking,
            "review_required": self.review_required,
            "actual_value": self.actual_value,
            "limit_value": self.limit_value,
            "metadata": self.metadata,
        }


class GovernanceConstraint(ABC):
    """Abstract base for governance constraints."""

    def __init__(self, name: str, blocking: bool = True):
        self.name = name
        self.blocking = blocking

    @abstractmethod
    def evaluate(self, request: DecisionRequest, context: DecisionContext) -> ConstraintResult:
        """Evaluate this constraint. Must be implemented by subclasses."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, blocking={self.blocking})"
