"""Allocation Decision — unified decision record with explainability.

Each decision captures: what changed, why, by how much,
and what constraints were checked.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class DecisionType(str, Enum):
    """Type of allocation decision."""
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    HOLD = "HOLD"
    FREEZE = "FREEZE"
    REJECT = "REJECT"
    ROTATE_IN = "ROTATE_IN"
    ROTATE_OUT = "ROTATE_OUT"
    LIQUIDATE = "LIQUIDATE"
    REBALANCE = "REBALANCE"
    DEFENSIVE = "DEFENSIVE"
    EMERGENCY = "EMERGENCY"


class DecisionSource(str, Enum):
    """Source of the allocation decision."""
    AUTONOMOUS = "AUTONOMOUS"
    SEMI_AUTO = "SEMI_AUTO"
    MANUAL = "MANUAL"
    GUARD = "GUARD"
    STRESS = "STRESS"
    EMERGENCY = "EMERGENCY"


@dataclass
class DecisionExplanation:
    """Explainable decision record."""
    primary_reasons: List[str] = field(default_factory=list)
    secondary_reasons: List[str] = field(default_factory=list)
    rejected_reasons: List[str] = field(default_factory=list)
    constraint_checks: Dict[str, bool] = field(default_factory=dict)
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    threshold_comparisons: Dict[str, Tuple[float, float]] = field(default_factory=dict)


@dataclass
class AllocationDecision:
    """Complete allocation decision for a single strategy.

    Captures the full decision context: scores, marginal analysis,
    constraints, and explainable reasoning.
    """

    strategy_id: str
    decision_type: DecisionType = DecisionType.HOLD
    source: DecisionSource = DecisionSource.AUTONOMOUS

    # Allocation state
    current_weight: float = 0.0
    target_weight: float = 0.0
    capital_delta: float = 0.0
    current_capital: float = 0.0
    target_capital: float = 0.0

    # Alpha & Risk
    expected_alpha: float = 0.0
    marginal_alpha: float = 0.0
    marginal_risk: float = 0.0
    marginal_cost: float = 0.0

    # Scores
    composite_score: float = 0.0
    alpha_score: float = 0.0
    risk_score: float = 0.0
    capacity_score: float = 0.0
    liquidity_score: float = 0.0
    impact_score: float = 0.0
    stress_score: float = 0.0
    survival_score: float = 0.0

    # Marginal analysis
    marginal_capacity: float = 0.0
    marginal_survival: float = 0.0
    risk_adjusted_mce: float = 0.0

    # Meta
    rank: int = 0
    decision_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    explanation: DecisionExplanation = field(default_factory=DecisionExplanation)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.decision_id:
            ts = self.timestamp.strftime("%Y%m%d%H%M%S%f")
            self.decision_id = f"dec-{ts}-{hash(self.strategy_id) & 0xFFFF:04x}"

    @property
    def weight_delta(self) -> float:
        return self.target_weight - self.current_weight

    @property
    def is_significant(self) -> bool:
        """Check if the decision represents a material change."""
        return abs(self.weight_delta) > 0.001 or abs(self.capital_delta) > 0.01

    def to_summary(self) -> str:
        """Generate a human-readable decision summary."""
        lines = [
            f"AllocationDecision [{self.decision_id}]",
            f"  Strategy: {self.strategy_id}",
            f"  Type: {self.decision_type.value} (source: {self.source.value})",
            f"  Weight: {self.current_weight:.4f} → {self.target_weight:.4f} "
            f"(Δ={self.weight_delta:+.4f})",
            f"  Capital: {self.current_capital:,.0f} → {self.target_capital:,.0f} "
            f"(Δ={self.capital_delta:+,.0f})",
            f"  Composite Score: {self.composite_score:.4f} (rank #{self.rank})",
            f"  Expected Alpha: {self.expected_alpha:.2%}",
            f"  Marginal Alpha: {self.marginal_alpha:.4f}",
            f"  Risk-Adjusted MCE: {self.risk_adjusted_mce:.4f}",
        ]
        if self.explanation.primary_reasons:
            lines.append("  Primary Reasons:")
            for r in self.explanation.primary_reasons:
                lines.append(f"    + {r}")
        return "\n".join(lines)


class AllocationDecisionBuilder:
    """Builder for constructing AllocationDecision objects."""

    def __init__(self, strategy_id: str):
        self._decision = AllocationDecision(strategy_id=strategy_id)

    def with_type(self, decision_type: DecisionType) -> "AllocationDecisionBuilder":
        self._decision.decision_type = decision_type
        return self

    def with_source(self, source: DecisionSource) -> "AllocationDecisionBuilder":
        self._decision.source = source
        return self

    def with_weights(self, current: float, target: float) -> "AllocationDecisionBuilder":
        self._decision.current_weight = current
        self._decision.target_weight = target
        self._decision.capital_delta = 0.0
        return self

    def with_alpha(self, expected: float, marginal: float = 0.0) -> "AllocationDecisionBuilder":
        self._decision.expected_alpha = expected
        self._decision.marginal_alpha = marginal
        return self

    def with_risk(self, risk_score: float, marginal_risk: float = 0.0) -> "AllocationDecisionBuilder":
        self._decision.risk_score = risk_score
        self._decision.marginal_risk = marginal_risk
        return self

    def with_scores(self, composite: float = 0.0, alpha: float = 0.0,
                    risk: float = 0.0, capacity: float = 0.0,
                    liquidity: float = 0.0, impact: float = 0.0,
                    stress: float = 0.0, survival: float = 0.0) -> "AllocationDecisionBuilder":
        self._decision.composite_score = composite
        self._decision.alpha_score = alpha
        self._decision.risk_score = risk
        self._decision.capacity_score = capacity
        self._decision.liquidity_score = liquidity
        self._decision.impact_score = impact
        self._decision.stress_score = stress
        self._decision.survival_score = survival
        return self

    def with_marginal(self, capacity: float = 0.0, cost: float = 0.0,
                      survival: float = 0.0, mce: float = 0.0) -> "AllocationDecisionBuilder":
        self._decision.marginal_capacity = capacity
        self._decision.marginal_cost = cost
        self._decision.marginal_survival = survival
        self._decision.risk_adjusted_mce = mce
        return self

    def with_capital(self, current: float, target: float) -> "AllocationDecisionBuilder":
        self._decision.current_capital = current
        self._decision.target_capital = target
        self._decision.capital_delta = target - current
        return self

    def with_rank(self, rank: int) -> "AllocationDecisionBuilder":
        self._decision.rank = rank
        return self

    def add_reason(self, reason: str, primary: bool = True) -> "AllocationDecisionBuilder":
        if primary:
            self._decision.explanation.primary_reasons.append(reason)
        else:
            self._decision.explanation.secondary_reasons.append(reason)
        return self

    def add_constraint_check(self, constraint: str, passed: bool) -> "AllocationDecisionBuilder":
        self._decision.explanation.constraint_checks[constraint] = passed
        return self

    def build(self) -> AllocationDecision:
        return self._decision
