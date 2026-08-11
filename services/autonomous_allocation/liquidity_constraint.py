"""Liquidity Constraint — limits allocation based on market liquidity.

If liquidity score is too low, max allocation is reduced
proportionally rather than blocking entirely.
"""

from typing import Any, Dict

from .allocation_constraint import (
    AllocationConstraint, ConstraintResult, ConstraintStatus, ConstraintType,
)


class LiquidityConstraint(AllocationConstraint):
    """Limits allocation based on liquidity scores.

    Liquidity Score → Max Allocation Adjustment:
        > 0.80  → 100% of normal max
        0.60-0.80 → 75%
        0.40-0.60 → 50%
        0.15-0.40 → 25%
        < 0.15  → BLOCK
    """

    def __init__(self, liquidity_scores: Dict[str, float] = None,
                 min_liquidity_score: float = 0.15,
                 base_max_allocation: Dict[str, float] = None):
        super().__init__("liquidity_constraint", ConstraintType.HARD)
        self._scores = liquidity_scores or {}
        self._min_score = min_liquidity_score
        self._base_max = base_max_allocation or {}

    def set_score(self, strategy_id: str, score: float) -> None:
        self._scores[strategy_id] = score

    def set_base_max(self, strategy_id: str, max_capital: float) -> None:
        self._base_max[strategy_id] = max_capital

    def get_adjusted_max(self, strategy_id: str) -> float:
        """Get liquidity-adjusted max allocation."""
        score = self._scores.get(strategy_id, 1.0)
        base = self._base_max.get(strategy_id, float("inf"))

        if score < self._min_score:
            return 0.0
        elif score >= 0.80:
            return base
        elif score >= 0.60:
            return base * 0.75
        elif score >= 0.40:
            return base * 0.50
        elif score >= 0.15:
            return base * 0.25
        return 0.0

    def check(self, allocation: Dict[str, Any]) -> ConstraintResult:
        allocations = allocation.get("allocations", {})
        violations = []

        for sid, capital in allocations.items():
            score = self._scores.get(sid, 1.0)
            if score < self._min_score:
                violations.append(f"{sid}: liquidity score {score:.2f} < min {self._min_score:.2f}")
                continue

            adj_max = self.get_adjusted_max(sid)
            if capital > adj_max:
                violations.append(
                    f"{sid}: {capital:,.0f} > adjusted max {adj_max:,.0f} (score={score:.2f})"
                )

        if violations:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.VIOLATED,
                violation_severity=min(1.0, len(violations) / max(1, len(allocations))),
                message=f"Liquidity violations: {'; '.join(violations)}",
                details={"liquidity_scores": dict(self._scores)},
            )

        return ConstraintResult(
            constraint_name=self.name,
            status=ConstraintStatus.SATISFIED,
            message="Liquidity constraints satisfied",
        )

    def check_weight(self, strategy_id: str, weight: float,
                     total_capital: float) -> ConstraintResult:
        capital = weight * total_capital
        score = self._scores.get(strategy_id, 1.0)

        if score < self._min_score:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.VIOLATED,
                value=score,
                limit=self._min_score,
                message=f"Strategy {strategy_id} liquidity score {score:.2f} < min {self._min_score:.2f}",
            )

        adj_max = self.get_adjusted_max(strategy_id)
        if capital > adj_max:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.VIOLATED,
                value=capital,
                limit=adj_max,
                message=f"Allocation {capital:,.0f} > liquidity-adj max {adj_max:,.0f}",
            )

        return ConstraintResult(
            constraint_name=self.name,
            status=ConstraintStatus.SATISFIED,
        )
