"""
Decision Governance — constraint evaluation and decision routing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .decision_context import DecisionContext
from .decision_request import DecisionRequest
from .governance_constraint import GovernanceConstraint, ConstraintResult


@dataclass
class DecisionGovernanceConfig:
    """Configuration for decision governance routing."""

    default_constraints: List[str] = field(default_factory=lambda: [
        "capital",
        "risk",
        "leverage",
        "liquidity",
        "concentration",
        "autonomy",
    ])
    strict_mode: bool = False


class DecisionGovernance:
    """
    Routes decisions through constraint evaluation.
    Separates the "what should we check?" from "how do we check it?".
    """

    def __init__(
        self,
        constraints: Optional[List[GovernanceConstraint]] = None,
        config: Optional[DecisionGovernanceConfig] = None,
    ):
        self._constraints: Dict[str, GovernanceConstraint] = {}
        self._config = config or DecisionGovernanceConfig()

        for c in (constraints or []):
            self._constraints[c.name] = c

    # ------------------------------------------------------------------
    # Constraint management
    # ------------------------------------------------------------------

    def register(self, constraint: GovernanceConstraint) -> None:
        self._constraints[constraint.name] = constraint

    def unregister(self, name: str) -> None:
        self._constraints.pop(name, None)

    def get(self, name: str) -> Optional[GovernanceConstraint]:
        return self._constraints.get(name)

    def list_constraints(self) -> List[GovernanceConstraint]:
        return list(self._constraints.values())

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate_constraints(
        self, request: DecisionRequest, context: DecisionContext
    ) -> List[ConstraintResult]:
        """Evaluate all registered constraints in priority order."""
        results: List[ConstraintResult] = []

        for constraint in self._constraints.values():
            try:
                result = constraint.evaluate(request, context)
                results.append(result)
            except Exception as exc:
                results.append(ConstraintResult(
                    constraint_name=constraint.name,
                    passed=False,
                    reason=f"Evaluation error: {exc}",
                    blocking=True if self._config.strict_mode else False,
                    review_required=True,
                ))

        return results

    def evaluate_named(
        self, request: DecisionRequest, context: DecisionContext, names: List[str]
    ) -> List[ConstraintResult]:
        """Evaluate only specific constraints by name."""
        results: List[ConstraintResult] = []
        for name in names:
            constraint = self._constraints.get(name)
            if constraint:
                try:
                    results.append(constraint.evaluate(request, context))
                except Exception as exc:
                    results.append(ConstraintResult(
                        constraint_name=name,
                        passed=False,
                        reason=f"Evaluation error: {exc}",
                        blocking=True,
                        review_required=True,
                    ))
        return results

    # ------------------------------------------------------------------
    # Convenience queries
    # ------------------------------------------------------------------

    def all_passed(self, results: List[ConstraintResult]) -> bool:
        return all(r.passed for r in results)

    def any_blocking(self, results: List[ConstraintResult]) -> bool:
        return any(r.blocking for r in results)

    def any_review(self, results: List[ConstraintResult]) -> bool:
        return any(r.review_required for r in results)

    def blocking_constraints(self, results: List[ConstraintResult]) -> List[ConstraintResult]:
        return [r for r in results if r.blocking]

    def failed_constraints(self, results: List[ConstraintResult]) -> List[ConstraintResult]:
        return [r for r in results if not r.passed]
