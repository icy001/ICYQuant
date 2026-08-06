"""RankIC Analysis — Spearman rank correlation for factor predictive power.

Supports::

    Spearman Rank, Rolling RankIC, Rank Stability

Suitable for non-linear relationships; more robust than Pearson IC.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RankICResult:
    """Rank Information Coefficient analysis result."""

    factor_name: str = ""
    mean_rankic: float = 0.0
    std_rankic: float = 0.0
    rankic_ir: float = 0.0
    rankic_positive_ratio: float = 0.0
    daily_rankic: List[float] = field(default_factory=list)
    rolling_rankic: Optional[List[float]] = None
    rank_stability: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "factor_name": self.factor_name,
            "mean_rankic": self.mean_rankic,
            "std_rankic": self.std_rankic,
            "rankic_ir": self.rankic_ir,
            "rankic_positive_ratio": self.rankic_positive_ratio,
            "daily_rankic_count": len(self.daily_rankic),
            "rank_stability": self.rank_stability,
            "metadata": self.metadata,
        }


class RankICAnalyzer:
    """Spearman Rank Information Coefficient analyzer.

    Computes Spearman rank correlation between factor values and
    forward returns. More robust to outliers and non-linearity.
    """

    def __init__(self, min_periods: int = 20) -> None:
        self._min_periods = min_periods

    def _rank(self, values: List[float]) -> List[float]:
        """Compute ranks (1-based, average for ties)."""
        n = len(values)
        indexed = list(enumerate(values))
        indexed.sort(key=lambda x: x[1])

        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n and indexed[j][1] == indexed[i][1]:
                j += 1
            avg_rank = (i + j - 1) / 2 + 1
            for k in range(i, j):
                ranks[indexed[k][0]] = avg_rank
            i = j

        return ranks

    def compute(
        self,
        factor_values: List[float],
        forward_returns: List[float],
        factor_name: str = "",
    ) -> RankICResult:
        """Compute single-period RankIC."""
        if not factor_values or not forward_returns:
            return RankICResult(factor_name=factor_name)

        n = min(len(factor_values), len(forward_returns))
        if n < 3:
            return RankICResult(factor_name=factor_name)

        factor_ranks = self._rank(list(factor_values[:n]))
        return_ranks = self._rank(list(forward_returns[:n]))

        # Pearson correlation of ranks = Spearman rank correlation
        mean_fr = sum(factor_ranks) / n
        mean_rr = sum(return_ranks) / n

        cov = sum(
            (f - mean_fr) * (r - mean_rr)
            for f, r in zip(factor_ranks, return_ranks)
        )
        var_f = sum((f - mean_fr) ** 2 for f in factor_ranks)
        var_r = sum((r - mean_rr) ** 2 for r in return_ranks)

        if var_f == 0 or var_r == 0:
            rankic = 0.0
        else:
            rankic = cov / ((var_f * var_r) ** 0.5)

        return RankICResult(
            factor_name=factor_name,
            mean_rankic=rankic,
            std_rankic=0.0,
            rankic_ir=0.0,
            rankic_positive_ratio=1.0 if rankic > 0 else 0.0,
            daily_rankic=[rankic],
        )

    def compute_time_series(
        self,
        factor_panel: Dict[str, List[float]],
        forward_returns_panel: Dict[str, List[float]],
        factor_name: str = "",
        rolling_window: int = 20,
    ) -> RankICResult:
        """Compute RankIC time series across multiple periods."""
        dates = sorted(set(factor_panel.keys()) & set(forward_returns_panel.keys()))
        if not dates:
            return RankICResult(factor_name=factor_name)

        daily_rankic: List[float] = []

        for date in dates:
            f_vals = factor_panel.get(date, [])
            r_vals = forward_returns_panel.get(date, [])
            if not f_vals or not r_vals:
                continue

            n = min(len(f_vals), len(r_vals))
            if n < self._min_periods:
                continue

            factor_ranks = self._rank(list(f_vals[:n]))
            return_ranks = self._rank(list(r_vals[:n]))

            mean_fr = sum(factor_ranks) / n
            mean_rr = sum(return_ranks) / n

            cov = sum(
                (f - mean_fr) * (r - mean_rr)
                for f, r in zip(factor_ranks, return_ranks)
            )
            var_f = sum((f - mean_fr) ** 2 for f in factor_ranks)
            var_r = sum((r - mean_rr) ** 2 for r in return_ranks)

            if var_f > 0 and var_r > 0:
                rankic = cov / ((var_f * var_r) ** 0.5)
                daily_rankic.append(rankic)

        if not daily_rankic:
            return RankICResult(factor_name=factor_name)

        n_ic = len(daily_rankic)
        mean_rankic = sum(daily_rankic) / n_ic
        variance = sum((ic - mean_rankic) ** 2 for ic in daily_rankic) / n_ic
        std_rankic = variance ** 0.5
        rankic_ir = mean_rankic / std_rankic if std_rankic > 0 else 0.0
        positive_ratio = sum(1 for ic in daily_rankic if ic > 0) / n_ic

        # Rolling RankIC
        rolling_rankic: List[float] = []
        if n_ic >= rolling_window:
            for i in range(rolling_window - 1, n_ic):
                window = daily_rankic[i - rolling_window + 1 : i + 1]
                rolling_rankic.append(sum(window) / rolling_window)

        # Rank stability: autocorrelation of daily rankic
        rank_stability = 0.0
        if n_ic > 1:
            lag1 = [daily_rankic[i] for i in range(1, n_ic)]
            lag0 = [daily_rankic[i] for i in range(n_ic - 1)]
            mean_lag1 = sum(lag1) / len(lag1)
            mean_lag0 = sum(lag0) / len(lag0)
            cov_stab = sum((a - mean_lag1) * (b - mean_lag0) for a, b in zip(lag1, lag0))
            var1 = sum((a - mean_lag1) ** 2 for a in lag1)
            var0 = sum((b - mean_lag0) ** 2 for b in lag0)
            if var1 > 0 and var0 > 0:
                rank_stability = cov_stab / ((var1 * var0) ** 0.5)

        return RankICResult(
            factor_name=factor_name,
            mean_rankic=mean_rankic,
            std_rankic=std_rankic,
            rankic_ir=rankic_ir,
            rankic_positive_ratio=positive_ratio,
            daily_rankic=daily_rankic,
            rolling_rankic=rolling_rankic,
            rank_stability=rank_stability,
        )
