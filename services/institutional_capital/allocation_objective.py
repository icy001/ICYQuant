"""
Allocation Objective — Unified multi-objective optimization target for capital distribution.

Supported objectives:
    Maximize Return, Maximize Sharpe, Maximize Risk-Adjusted Return,
    Maximize Capital Efficiency, Minimize Drawdown, Minimize Correlation,
    Minimize Tail Risk.

Composite:
    Objective = Return - λ·Risk - γ·Correlation - δ·Cost + ε·Efficiency
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class ObjectiveType(str, Enum):
    """Type of optimization objective."""
    MAX_RETURN = "max_return"
    MAX_SHARPE = "max_sharpe"
    MAX_RISK_ADJUSTED_RETURN = "max_risk_adjusted_return"
    MAX_CAPITAL_EFFICIENCY = "max_capital_efficiency"
    MIN_DRAWDOWN = "min_drawdown"
    MIN_CORRELATION = "min_correlation"
    MIN_TAIL_RISK = "min_tail_risk"
    COMPOSITE = "composite"


class Direction(str, Enum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


@dataclass
class ObjectiveTerm:
    """A single term in a composite objective."""

    term_id: str = field(default_factory=lambda: f"OT-{uuid.uuid4().hex[:8]}")
    name: str = ""
    field: str = ""                     # e.g. "expected_return", "risk", "correlation"
    coefficient: float = 1.0            # weight of this term
    direction: Direction = Direction.MAXIMIZE
    transform: Optional[str] = None     # optional transform: "log", "sqrt", "square"
    cap: Optional[float] = None         # maximum absolute contribution

    def evaluate(self, value: float) -> float:
        """Compute the contribution of this term."""
        if self.transform == "log":
            value = self._safe_log(value)
        elif self.transform == "sqrt":
            value = value ** 0.5 if value >= 0 else 0
        elif self.transform == "square":
            value = value ** 2
        contribution = self.coefficient * value
        if self.cap is not None:
            contribution = max(-self.cap, min(self.cap, contribution))
        if self.direction == Direction.MINIMIZE:
            contribution = -contribution
        return contribution

    @staticmethod
    def _safe_log(x: float) -> float:
        import math
        if x <= 0:
            return -10.0
        return math.log(x)


@dataclass
class AllocationObjective:
    """Unified capital allocation objective."""

    objective_id: str = field(default_factory=lambda: f"AO-{uuid.uuid4().hex[:8]}")
    name: str = ""
    objective_type: ObjectiveType = ObjectiveType.COMPOSITE
    terms: List[ObjectiveTerm] = field(default_factory=list)

    def evaluate(self, metrics: Dict[str, float]) -> float:
        """Evaluate objective score from a metrics dictionary."""
        if not self.terms:
            return 0.0
        return sum(t.evaluate(metrics.get(t.field, 0.0)) for t in self.terms)

    def evaluate_multi(self, candidates: List[Dict[str, float]]) -> List[float]:
        """Score a list of candidate allocations."""
        return [self.evaluate(c) for c in candidates]

    def best(self, candidates: List[Dict[str, float]]) -> Tuple[int, float]:
        """Return (index, score) of the best candidate."""
        scores = self.evaluate_multi(candidates)
        if not scores:
            return -1, float("-inf")
        best_idx = max(range(len(scores)), key=lambda i: scores[i])
        return best_idx, scores[best_idx]


class ObjectiveFactory:
    """Factory for common institutional allocation objectives."""

    @staticmethod
    def max_return() -> AllocationObjective:
        return AllocationObjective(
            name="MaxReturn",
            objective_type=ObjectiveType.MAX_RETURN,
            terms=[ObjectiveTerm(name="Return", field="expected_return", coefficient=1.0)],
        )

    @staticmethod
    def max_sharpe(risk_free_rate: float = 0.02) -> AllocationObjective:
        return AllocationObjective(
            name="MaxSharpe",
            objective_type=ObjectiveType.MAX_SHARPE,
            terms=[
                ObjectiveTerm(name="Return", field="expected_return", coefficient=1.0),
                ObjectiveTerm(name="RiskFree", field="risk_free_rate", coefficient=-1.0),
                ObjectiveTerm(name="Risk", field="volatility", coefficient=-1.0, transform="square"),
            ],
        )

    @staticmethod
    def max_risk_adjusted_return(lambda_risk: float = 2.0) -> AllocationObjective:
        return AllocationObjective(
            name="MaxRiskAdjustedReturn",
            objective_type=ObjectiveType.MAX_RISK_ADJUSTED_RETURN,
            terms=[
                ObjectiveTerm(name="Return", field="expected_return", coefficient=1.0),
                ObjectiveTerm(name="RiskPenalty", field="volatility", coefficient=-lambda_risk),
            ],
        )

    @staticmethod
    def max_capital_efficiency() -> AllocationObjective:
        return AllocationObjective(
            name="MaxCapitalEfficiency",
            objective_type=ObjectiveType.MAX_CAPITAL_EFFICIENCY,
            terms=[
                ObjectiveTerm(name="Efficiency", field="capital_efficiency", coefficient=1.0),
                ObjectiveTerm(name="Utilization", field="capital_utilization", coefficient=0.3),
            ],
        )

    @staticmethod
    def institutional_composite(
        lambda_risk: float = 1.5,
        gamma_correlation: float = 0.8,
        delta_cost: float = 0.3,
        epsilon_efficiency: float = 0.5,
    ) -> AllocationObjective:
        """Composite institutional objective.

        Score = Return - λ·Risk - γ·Correlation - δ·Cost + ε·Efficiency
        """
        return AllocationObjective(
            name="InstitutionalComposite",
            objective_type=ObjectiveType.COMPOSITE,
            terms=[
                ObjectiveTerm(name="Return", field="expected_return", coefficient=1.0),
                ObjectiveTerm(name="RiskPenalty", field="volatility", coefficient=-lambda_risk),
                ObjectiveTerm(name="CorrelationPenalty", field="avg_correlation", coefficient=-gamma_correlation),
                ObjectiveTerm(name="CostPenalty", field="transaction_cost", coefficient=-delta_cost),
                ObjectiveTerm(name="Efficiency", field="capital_efficiency", coefficient=epsilon_efficiency),
            ],
        )

    @staticmethod
    def min_drawdown() -> AllocationObjective:
        return AllocationObjective(
            name="MinDrawdown",
            objective_type=ObjectiveType.MIN_DRAWDOWN,
            terms=[
                ObjectiveTerm(name="Drawdown", field="max_drawdown", coefficient=1.0,
                              direction=Direction.MINIMIZE),
            ],
        )

    @staticmethod
    def min_tail_risk() -> AllocationObjective:
        return AllocationObjective(
            name="MinTailRisk",
            objective_type=ObjectiveType.MIN_TAIL_RISK,
            terms=[
                ObjectiveTerm(name="CVaR", field="cvar_95", coefficient=1.0,
                              direction=Direction.MINIMIZE),
                ObjectiveTerm(name="TailLoss", field="expected_shortfall", coefficient=0.8,
                              direction=Direction.MINIMIZE),
            ],
        )
