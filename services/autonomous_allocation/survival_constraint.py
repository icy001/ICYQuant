"""Survival Constraint — the most critical constraint.

Ensures post-allocation survival score meets minimum threshold.
Even if a candidate allocation has higher expected return,
it MUST be rejected if it reduces capital survival below threshold.

Core principle:
> An allocation that reduces survival probability cannot be executed,
> regardless of its alpha improvement.
"""

from typing import Any, Dict

from .allocation_constraint import (
    AllocationConstraint, ConstraintResult, ConstraintStatus, ConstraintType,
)


class SurvivalConstraint(AllocationConstraint):
    """Ensures allocation preserves capital survival.

    This is the absolute constraint — it overrides all others.
    Type: ABSOLUTE ensures it cannot be bypassed.
    """

    def __init__(self, minimum_survival_score: float = 0.70,
                 minimum_buffer_ratio: float = 0.05,
                 minimum_reserve_ratio: float = 0.10,
                 max_risk_of_ruin: float = 0.05):
        super().__init__("survival_constraint", ConstraintType.ABSOLUTE)
        self._min_survival = minimum_survival_score
        self._min_buffer = minimum_buffer_ratio
        self._min_reserve = minimum_reserve_ratio
        self._max_ruin = max_risk_of_ruin

    def set_minimum(self, score: float) -> None:
        self._min_survival = score

    @property
    def minimum_threshold(self) -> float:
        return self._min_survival

    def check(self, allocation: Dict[str, Any]) -> ConstraintResult:
        survival_score = allocation.get("survival_score", 0.0)
        pre_score = allocation.get("pre_allocation_survival", survival_score)
        buffer_ratio = allocation.get("buffer_ratio", 0.0)
        reserve_ratio = allocation.get("reserve_ratio", 0.0)
        risk_of_ruin = allocation.get("risk_of_ruin", 0.0)

        violations = []

        # Check 1: Post-allocation survival ≥ minimum
        if survival_score < self._min_survival:
            violations.append(
                f"Survival score {survival_score:.3f} < minimum {self._min_survival:.3f}"
            )

        # Check 2: Allocation must not degrade survival below threshold
        if survival_score < self._min_survival and pre_score >= self._min_survival:
            violations.append(
                f"Allocation reduces survival from {pre_score:.3f} to {survival_score:.3f} "
                f"(below {self._min_survival:.3f})"
            )

        # Check 3: Buffer adequacy
        if buffer_ratio < self._min_buffer:
            violations.append(
                f"Buffer ratio {buffer_ratio:.2%} < min {self._min_buffer:.2%}"
            )

        # Check 4: Reserve adequacy
        if reserve_ratio < self._min_reserve:
            violations.append(
                f"Reserve ratio {reserve_ratio:.2%} < min {self._min_reserve:.2%}"
            )

        # Check 5: Risk of ruin
        if risk_of_ruin > self._max_ruin:
            violations.append(
                f"Risk of ruin {risk_of_ruin:.2%} > max {self._max_ruin:.2%}"
            )

        if violations:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.VIOLATED,
                value=survival_score,
                limit=self._min_survival,
                margin=survival_score - self._min_survival,
                violation_severity=1.0,  # Absolute violation = maximum severity
                message=f"SURVIVAL VIOLATION: {'; '.join(violations)}",
                details={
                    "survival_score": survival_score,
                    "pre_allocation_survival": pre_score,
                    "buffer_ratio": buffer_ratio,
                    "reserve_ratio": reserve_ratio,
                    "risk_of_ruin": risk_of_ruin,
                },
            )

        return ConstraintResult(
            constraint_name=self.name,
            status=ConstraintStatus.SATISFIED,
            value=survival_score,
            limit=self._min_survival,
            margin=survival_score - self._min_survival,
            message=f"Survival score {survival_score:.3f} ≥ threshold {self._min_survival:.3f}",
        )
