"""Survival Score — scores strategy survival contribution for allocation.

Evaluates whether an allocation improves or degrades capital survival:
- Post-allocation survival probability
- Capital buffer adequacy
- Recovery time under stress
- Tail risk contribution
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class SurvivalScoreResult:
    """Survival scoring result for a strategy."""
    strategy_id: str
    score: float = 0.0  # 0-1, higher = better survival contribution
    pre_allocation_score: float = 0.0
    post_allocation_score: float = 0.0
    survival_improvement: float = 0.0
    capital_buffer_adequacy: float = 0.0
    recovery_time_days: float = 0.0
    tail_risk_contribution: float = 0.0
    risk_of_ruin: float = 0.0
    minimum_threshold: float = 0.70
    meets_threshold: bool = True
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        return (
            f"SurvivalScore[{self.strategy_id}] score={self.score:.3f} "
            f"pre={self.pre_allocation_score:.2f}→post={self.post_allocation_score:.2f} "
            f"(Δ={self.survival_improvement:+.3f}) meets_threshold={self.meets_threshold}"
        )


class SurvivalScorer:
    """Scores strategies based on capital survival contribution.

    The most critical constraint: an allocation that reduces survival
    must be rejected, regardless of its alpha improvement.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._minimum_threshold = self._config.get("minimum_threshold", 0.70)
        self._buffer_weight = self._config.get("buffer_weight", 0.25)
        self._improvement_weight = self._config.get("improvement_weight", 0.35)
        self._tail_weight = self._config.get("tail_weight", 0.25)
        self._recovery_weight = self._config.get("recovery_weight", 0.15)

    @property
    def minimum_threshold(self) -> float:
        return self._minimum_threshold

    def score(self, strategy_id: str,
              pre_allocation_score: float = 0.75,
              post_allocation_score: float = 0.75,
              capital_buffer_adequacy: float = 0.5,
              recovery_time_days: float = 30.0,
              tail_risk_contribution: float = 0.0,
              risk_of_ruin: float = 0.01,
              minimum_threshold: Optional[float] = None) -> SurvivalScoreResult:
        """Compute survival score.

        Score = w_imp * improvement + w_buf * buffer + w_tail * (1-tail) + w_rec * (1-rec_time)
        """
        threshold = minimum_threshold or self._minimum_threshold
        improvement = post_allocation_score - pre_allocation_score

        # Normalize improvement (-0.3 to +0.3 → 0 to 1)
        norm_improvement = (improvement + 0.3) / 0.6
        norm_improvement = max(0.0, min(1.0, norm_improvement))

        # Buffer adequacy: higher is better
        buffer_score = min(1.0, capital_buffer_adequacy)

        # Tail risk: lower is better
        tail_score = max(0.0, 1.0 - tail_risk_contribution / 0.10)

        # Recovery time: shorter is better (normalize to 90 days max)
        rec_score = max(0.0, 1.0 - recovery_time_days / 90.0)

        score = (
            self._improvement_weight * norm_improvement +
            self._buffer_weight * buffer_score +
            self._tail_weight * tail_score +
            self._recovery_weight * rec_score
        )

        # Adjust for risk of ruin
        if risk_of_ruin > 0.05:
            score *= 0.5

        meets = post_allocation_score >= threshold

        return SurvivalScoreResult(
            strategy_id=strategy_id,
            score=max(0.0, min(1.0, score)),
            pre_allocation_score=pre_allocation_score,
            post_allocation_score=post_allocation_score,
            survival_improvement=improvement,
            capital_buffer_adequacy=capital_buffer_adequacy,
            recovery_time_days=recovery_time_days,
            tail_risk_contribution=tail_risk_contribution,
            risk_of_ruin=risk_of_ruin,
            minimum_threshold=threshold,
            meets_threshold=meets,
        )

    def compute_from_capital(self, strategy_id: str,
                              total_capital: float,
                              deployed_capital: float,
                              reserve: float,
                              buffer: float,
                              max_drawdown: float,
                              expected_return: float,
                              volatility: float) -> SurvivalScoreResult:
        """Compute survival score from capital structure and risk metrics."""
        # Pre-allocation survival
        pre_score = self._compute_survival_probability(
            total_capital, deployed_capital, reserve, buffer,
            max_drawdown, expected_return, volatility,
        )

        # Post-allocation: simulate adding capital
        new_deployed = deployed_capital * 1.10  # Simulate 10% more deployed
        post_score = self._compute_survival_probability(
            total_capital, new_deployed, reserve, buffer,
            max_drawdown, expected_return, volatility,
        )

        buffer_adequacy = (reserve + buffer) / max(1, total_capital)
        recovery_time = max_drawdown / max(0.0001, abs(expected_return)) * 252

        return self.score(
            strategy_id=strategy_id,
            pre_allocation_score=pre_score,
            post_allocation_score=post_score,
            capital_buffer_adequacy=buffer_adequacy,
            recovery_time_days=recovery_time,
            tail_risk_contribution=volatility * 2.33,
            risk_of_ruin=max_drawdown / 0.50,
        )

    def _compute_survival_probability(self, capital: float, deployed: float,
                                       reserve: float, buffer: float,
                                       max_drawdown: float, expected_return: float,
                                       volatility: float) -> float:
        """Compute crude survival probability."""
        if capital <= 0:
            return 0.0

        # Capital cushion ratio
        cushion = (reserve + buffer) / max(1, capital)

        # Risk-adjusted return
        risk_adj_return = expected_return / max(0.01, volatility) if volatility > 0 else 1.0

        # Drawdown resilience
        dd_resilience = max(0.0, 1.0 - max_drawdown / 0.50)

        # Composite
        survival = 0.4 * cushion + 0.3 * min(1.0, risk_adj_return / 2.0) + 0.3 * dd_resilience

        return max(0.0, min(1.0, survival))

    def batch_score(self, strategies: Dict[str, Dict[str, Any]]) -> List[SurvivalScoreResult]:
        """Score multiple strategies at once."""
        results = []
        for sid, params in strategies.items():
            if all(k in params for k in ("total_capital", "deployed_capital")):
                result = self.compute_from_capital(strategy_id=sid, **params)
            else:
                result = self.score(strategy_id=sid, **params)
            results.append(result)
        return results
