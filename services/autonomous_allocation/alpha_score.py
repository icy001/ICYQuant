"""Alpha Score — scores strategy alpha quality for allocation decisions.

Evaluates:
- Expected alpha magnitude
- Alpha consistency/stability
- Alpha trend (improving/decaying)
- Information ratio
- Signal confidence
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class AlphaScoreResult:
    """Alpha scoring result for a strategy."""
    strategy_id: str
    score: float = 0.0  # 0-1
    expected_alpha: float = 0.0
    alpha_volatility: float = 0.0
    information_ratio: float = 0.0
    consistency: float = 0.0  # Hit rate of alpha predictions
    trend_score: float = 0.0  # +1 if improving, -1 if decaying
    confidence: float = 0.0  # Model confidence
    window_days: int = 60
    sample_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        return (
            f"AlphaScore[{self.strategy_id}] score={self.score:.3f} "
            f"alpha={self.expected_alpha:.2%} IR={self.information_ratio:.2f} "
            f"confidence={self.confidence:.2%}"
        )


class AlphaScorer:
    """Scores strategies based on alpha quality for allocation purposes."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._alpha_weight = self._config.get("alpha_weight", 0.40)
        self._ir_weight = self._config.get("ir_weight", 0.25)
        self._consistency_weight = self._config.get("consistency_weight", 0.20)
        self._trend_weight = self._config.get("trend_weight", 0.15)

    def score(self, strategy_id: str,
              expected_alpha: float = 0.0,
              alpha_volatility: float = 0.0,
              information_ratio: float = 0.0,
              consistency: float = 0.5,
              trend_score: float = 0.0,
              confidence: float = 0.5,
              window_days: int = 60,
              sample_count: int = 0) -> AlphaScoreResult:
        """Compute alpha score for a strategy.

        Score = w_α·norm_alpha + w_ir·norm_ir + w_cons·consistency + w_trend·norm_trend
        """
        # Normalize alpha to 0-1 (assume ~20% max is excellent)
        norm_alpha = min(1.0, max(0.0, expected_alpha / 0.20))

        # Normalize information ratio (IR > 2.0 is excellent)
        norm_ir = min(1.0, max(0.0, information_ratio / 2.0))

        # Normalize trend (-1 to +1 → 0 to 1)
        norm_trend = (trend_score + 1.0) / 2.0

        score = (
            self._alpha_weight * norm_alpha +
            self._ir_weight * norm_ir +
            self._consistency_weight * consistency +
            self._trend_weight * norm_trend
        )

        # Scale by confidence
        score *= (0.5 + 0.5 * confidence)

        return AlphaScoreResult(
            strategy_id=strategy_id,
            score=max(0.0, min(1.0, score)),
            expected_alpha=expected_alpha,
            alpha_volatility=alpha_volatility,
            information_ratio=information_ratio,
            consistency=consistency,
            trend_score=trend_score,
            confidence=confidence,
            window_days=window_days,
            sample_count=sample_count,
        )

    def score_from_returns(self, strategy_id: str,
                           daily_returns: List[float],
                           benchmark_returns: Optional[List[float]] = None,
                           risk_free_rate: float = 0.02) -> AlphaScoreResult:
        """Compute alpha score from raw return series."""
        if not daily_returns:
            return AlphaScoreResult(strategy_id=strategy_id)

        n = len(daily_returns)
        avg_return = sum(daily_returns) / n

        # Annualized
        annual_return = avg_return * 252
        excess = annual_return - risk_free_rate

        # Volatility
        var = sum((r - avg_return) ** 2 for r in daily_returns) / max(1, n - 1)
        vol = var ** 0.5 * (252 ** 0.5)

        # Information ratio
        ir = excess / vol if vol > 0 else 0.0

        # Consistency: fraction of positive days
        consistency = sum(1 for r in daily_returns if r > 0) / n

        # Trend: compare second half to first half
        mid = n // 2
        if mid > 0 and n > mid:
            first_half_avg = sum(daily_returns[:mid]) / mid
            second_half_avg = sum(daily_returns[mid:]) / (n - mid)
            diff = second_half_avg - first_half_avg
            trend = min(1.0, max(-1.0, diff / max(0.0001, abs(first_half_avg))))
        else:
            trend = 0.0

        return self.score(
            strategy_id=strategy_id,
            expected_alpha=excess,
            alpha_volatility=vol,
            information_ratio=ir,
            consistency=consistency,
            trend_score=trend,
            confidence=min(1.0, n / 60.0),
            window_days=n,
            sample_count=n,
        )

    def batch_score(self, strategies: Dict[str, Dict[str, Any]]) -> List[AlphaScoreResult]:
        """Score multiple strategies at once."""
        results = []
        for sid, params in strategies.items():
            if "daily_returns" in params:
                result = self.score_from_returns(
                    strategy_id=sid,
                    daily_returns=params["daily_returns"],
                )
            else:
                result = self.score(strategy_id=sid, **params)
            results.append(result)
        return results
