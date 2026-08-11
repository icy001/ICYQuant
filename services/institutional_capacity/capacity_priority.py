"""
Capacity Priority — Ranks strategies for capacity allocation.

Priority score based on: Expected Alpha, Impact cost, Margin efficiency, etc.

Example:
    A: Alpha=15%, Impact=3bps → Score=0.91
    B: Alpha=13%, Impact=8bps → Score=0.72
    C: Alpha=10%, Impact=15bps → Score=0.44
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CapacityPriorityScore:
    """Capacity priority score for a strategy."""

    score_id: str = field(default_factory=lambda: f"CP-{uuid.uuid4().hex[:8]}")
    strategy_id: str = ""
    asset: str = ""

    # Components
    alpha_score: float = 0.0             # normalized expected alpha
    impact_score: float = 0.0            # inverse of impact cost
    efficiency_score: float = 0.0        # capital efficiency
    risk_score: float = 0.0              # risk-adjusted
    correlation_score: float = 0.0       # diversification benefit

    # Weights
    alpha_weight: float = 0.35
    impact_weight: float = 0.25
    efficiency_weight: float = 0.20
    risk_weight: float = 0.10
    correlation_weight: float = 0.10

    # Result
    total_score: float = 0.0

    def compute(self) -> float:
        self.total_score = (
            self.alpha_score * self.alpha_weight +
            self.impact_score * self.impact_weight +
            self.efficiency_score * self.efficiency_weight +
            self.risk_score * self.risk_weight +
            self.correlation_score * self.correlation_weight
        )
        return self.total_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score_id": self.score_id,
            "strategy_id": self.strategy_id,
            "asset": self.asset,
            "alpha_score": self.alpha_score,
            "impact_score": self.impact_score,
            "total_score": self.total_score,
        }


class CapacityPriority:
    """Computes capacity allocation priority scores."""

    def score(
        self, strategy_id: str, asset: str,
        expected_alpha_pct: float = 0.0,
        expected_impact_bps: float = 0.0,
        capital_efficiency: float = 0.0,
        risk_contribution: float = 0.0,
        correlation_to_portfolio: float = 0.0,
    ) -> CapacityPriorityScore:
        s = CapacityPriorityScore(strategy_id=strategy_id, asset=asset)

        # Normalize alpha: 0-1 where 20% annual = 1.0
        s.alpha_score = min(1.0, max(0.0, expected_alpha_pct / 0.20))

        # Impact: lower impact = higher score
        s.impact_score = max(0.0, 1.0 - expected_impact_bps / 30.0)

        # Efficiency
        s.efficiency_score = min(1.0, max(0.0, capital_efficiency))

        # Risk: lower risk contribution = higher score
        s.risk_score = max(0.0, 1.0 - risk_contribution)

        # Correlation: lower correlation = higher diversification = higher score
        s.correlation_score = max(0.0, 1.0 - correlation_to_portfolio)

        s.compute()
        return s

    def rank(self, scores: List[CapacityPriorityScore]) -> List[CapacityPriorityScore]:
        return sorted(scores, key=lambda s: s.total_score, reverse=True)
