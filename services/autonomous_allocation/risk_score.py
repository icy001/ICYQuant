"""Risk Score — scores strategy risk efficiency for allocation decisions.

Evaluates risk-adjusted return quality:
- Sharpe ratio
- Sortino ratio
- Maximum drawdown
- Tail risk (CVaR)
- Volatility scaling
- Correlation contribution
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class RiskScoreResult:
    """Risk scoring result for a strategy."""
    strategy_id: str
    score: float = 0.0  # 0-1, higher = better risk efficiency
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    tail_risk: float = 0.0  # CVaR
    correlation_contribution: float = 0.0
    risk_efficiency: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        return (
            f"RiskScore[{self.strategy_id}] score={self.score:.3f} "
            f"Sharpe={self.sharpe_ratio:.2f} Sortino={self.sortino_ratio:.2f} "
            f"MDD={self.max_drawdown:.2%}"
        )


class RiskScorer:
    """Scores strategies based on risk-adjusted return quality."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._sharpe_weight = self._config.get("sharpe_weight", 0.30)
        self._sortino_weight = self._config.get("sortino_weight", 0.20)
        self._mdd_weight = self._config.get("mdd_weight", 0.20)
        self._tail_weight = self._config.get("tail_weight", 0.15)
        self._correlation_weight = self._config.get("correlation_weight", 0.15)

    def score(self, strategy_id: str,
              sharpe_ratio: float = 0.0,
              sortino_ratio: float = 0.0,
              max_drawdown: float = 0.0,
              volatility: float = 0.0,
              tail_risk: float = 0.0,
              correlation_contribution: float = 0.0,
              risk_efficiency: float = 0.5) -> RiskScoreResult:
        """Compute risk score for a strategy.

        Score = w_s·norm_sharpe + w_so·norm_sortino + w_m·norm_mdd
                + w_t·norm_tail + w_c·norm_corr
        """
        # Normalize Sharpe (2.0+ is excellent)
        norm_sharpe = min(1.0, max(0.0, sharpe_ratio / 2.0))

        # Normalize Sortino
        norm_sortino = min(1.0, max(0.0, sortino_ratio / 2.5))

        # Normalize MDD (0% = best, 50%+ = worst)
        norm_mdd = max(0.0, 1.0 - max_drawdown / 0.50)

        # Normalize tail risk (0 = best)
        norm_tail = max(0.0, 1.0 - tail_risk / 0.10)

        # Normalize correlation contribution (0 = best, uncorrelated)
        norm_corr = max(0.0, 1.0 - correlation_contribution)

        score = (
            self._sharpe_weight * norm_sharpe +
            self._sortino_weight * norm_sortino +
            self._mdd_weight * norm_mdd +
            self._tail_weight * norm_tail +
            self._correlation_weight * norm_corr
        )

        # Blend with risk efficiency
        score = 0.7 * score + 0.3 * risk_efficiency

        return RiskScoreResult(
            strategy_id=strategy_id,
            score=max(0.0, min(1.0, score)),
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            volatility=volatility,
            tail_risk=tail_risk,
            correlation_contribution=correlation_contribution,
            risk_efficiency=risk_efficiency,
        )

    def score_from_returns(self, strategy_id: str,
                           daily_returns: List[float],
                           risk_free_rate: float = 0.02) -> RiskScoreResult:
        """Compute risk score from raw return series."""
        if not daily_returns:
            return RiskScoreResult(strategy_id=strategy_id)

        n = len(daily_returns)
        avg_return = sum(daily_returns) / n
        annual_return = avg_return * 252
        excess = annual_return - risk_free_rate

        # Volatility
        var = sum((r - avg_return) ** 2 for r in daily_returns) / max(1, n - 1)
        vol = var ** 0.5 * (252 ** 0.5)

        # Sharpe
        sharpe = excess / vol if vol > 0 else 0.0

        # Sortino
        downside = [min(r, 0) for r in daily_returns]
        downside_var = sum(r ** 2 for r in downside) / max(1, len(downside) - 1)
        downside_vol = downside_var ** 0.5 * (252 ** 0.5)
        sortino = excess / downside_vol if downside_vol > 0 else 0.0

        # Max drawdown
        peak = daily_returns[0]
        mdd = 0.0
        for r in daily_returns:
            peak = max(peak, r)
            mdd = min(mdd, r - peak)
        mdd = abs(mdd)

        # Tail risk (CVaR at 5%)
        sorted_returns = sorted(daily_returns)
        tail_cutoff = max(1, int(n * 0.05))
        tail_returns = sorted_returns[:tail_cutoff]
        tail_risk = abs(sum(tail_returns) / len(tail_returns)) if tail_returns else 0.0

        return self.score(
            strategy_id=strategy_id,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=mdd,
            volatility=vol,
            tail_risk=tail_risk,
        )

    def batch_score(self, strategies: Dict[str, Dict[str, Any]]) -> List[RiskScoreResult]:
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
