"""Impact Score — scores expected market impact for allocation decisions.

Evaluates:
- Expected market impact in bps
- Temporary vs permanent impact split
- Impact curve steepness
- Impact budget consumption
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ImpactScoreResult:
    """Market impact scoring result for a strategy."""
    strategy_id: str
    score: float = 0.0  # 0-1, higher = lower impact
    expected_impact_bps: float = 0.0
    temporary_impact_bps: float = 0.0
    permanent_impact_bps: float = 0.0
    impact_budget_consumed: float = 0.0
    impact_budget_limit: float = 0.0
    urgency_score: float = 1.0  # How urgent the trade is
    max_order_at_impact: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        return (
            f"ImpactScore[{self.strategy_id}] score={self.score:.3f} "
            f"impact={self.expected_impact_bps:.1f}bps "
            f"budget={self.impact_budget_consumed:.1f}/{self.impact_budget_limit:.1f}"
        )


class ImpactScorer:
    """Scores strategies based on expected market impact.

    Higher score = lower expected impact per unit of capital.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._impact_threshold_bps = self._config.get("impact_threshold_bps", 15.0)
        self._budget_weight = self._config.get("budget_weight", 0.30)
        self._urgency_weight = self._config.get("urgency_weight", 0.10)

    def score(self, strategy_id: str,
              expected_impact_bps: float = 0.0,
              temporary_impact_bps: float = 0.0,
              permanent_impact_bps: float = 0.0,
              impact_budget_consumed: float = 0.0,
              impact_budget_limit: float = 15.0,
              urgency_score: float = 1.0,
              max_order_at_impact: float = 0.0) -> ImpactScoreResult:
        """Compute impact score.

        Score = 1 - normalized_impact, scaled by budget usage and urgency.
        """
        # Normalize impact: 0bps = perfect, threshold+ = worst
        norm_impact = min(1.0, expected_impact_bps / max(1.0, self._impact_threshold_bps))

        # Budget usage penalty
        budget_ratio = (impact_budget_consumed / max(1.0, impact_budget_limit)
                        if impact_budget_limit > 0 else 1.0)
        budget_score = max(0.0, 1.0 - budget_ratio)

        # Base score = 1 - normalized impact
        base_score = 1.0 - norm_impact

        score = (
            (1.0 - self._budget_weight - self._urgency_weight) * base_score +
            self._budget_weight * budget_score +
            self._urgency_weight * urgency_score
        )

        return ImpactScoreResult(
            strategy_id=strategy_id,
            score=max(0.0, min(1.0, score)),
            expected_impact_bps=expected_impact_bps,
            temporary_impact_bps=temporary_impact_bps,
            permanent_impact_bps=permanent_impact_bps,
            impact_budget_consumed=impact_budget_consumed,
            impact_budget_limit=impact_budget_limit,
            urgency_score=urgency_score,
            max_order_at_impact=max_order_at_impact,
        )

    def score_from_sqrt_model(self, strategy_id: str,
                               order_size: float,
                               daily_volume: float,
                               volatility: float,
                               participation_rate: float = 0.0,
                               scale_factor: float = 1.0,
                               impact_budget_limit: float = 15.0) -> ImpactScoreResult:
        """Compute impact score from square-root market impact model.

        Impact = σ * scale * (Q/V)^0.5  in bps
        """
        if daily_volume <= 0:
            return ImpactScoreResult(strategy_id=strategy_id, score=1.0)

        vol_bps = volatility * 10000  # Convert to bps
        participation = order_size / daily_volume
        impact_bps = vol_bps * scale_factor * (participation ** 0.5)

        # Split: 60% temporary, 40% permanent
        temp_impact = impact_bps * 0.60
        perm_impact = impact_bps * 0.40

        return self.score(
            strategy_id=strategy_id,
            expected_impact_bps=impact_bps,
            temporary_impact_bps=temp_impact,
            permanent_impact_bps=perm_impact,
            impact_budget_consumed=impact_bps,
            impact_budget_limit=impact_budget_limit,
        )

    def batch_score(self, strategies: Dict[str, Dict[str, Any]]) -> List[ImpactScoreResult]:
        """Score multiple strategies at once."""
        results = []
        for sid, params in strategies.items():
            if all(k in params for k in ("order_size", "daily_volume", "volatility")):
                result = self.score_from_sqrt_model(strategy_id=sid, **params)
            else:
                result = self.score(strategy_id=sid, **params)
            results.append(result)
        return results
