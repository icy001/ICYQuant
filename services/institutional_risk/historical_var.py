"""HistoricalVar — empirical historical VaR computation.

Computes VaR from historical return observations using the
empirical percentile method.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class HistoricalVaRResult:
    """Historical VaR result with rich metadata."""

    var_95: float = 0.0
    var_99: float = 0.0
    var_995: float = 0.0
    var_999: float = 0.0
    min_return: float = 0.0
    max_return: float = 0.0
    mean_return: float = 0.0
    std_return: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    sample_size: int = 0
    window_days: int = 252
    exceedance_ratio_95: float = 0.0
    exceedance_ratio_99: float = 0.0
    worst_5_losses: List[float] = field(default_factory=list)


class HistoricalVaREngine:
    """Empirical Historical VaR engine.

    Computes VaR by ordering historical returns and taking
    the appropriate percentile. Most transparent method.

    Usage::

        engine = HistoricalVaREngine(window=504)
        result = engine.compute(daily_returns)
        print(f"Historical VaR 99%: {result.var_99:.0f}")
    """

    def __init__(self, window: int = 252):
        self._window = window

    def compute(
        self,
        returns: List[float],
        labels: Optional[List[str]] = None,
    ) -> HistoricalVaRResult:
        """Compute historical VaR from return series.

        Args:
            returns: list of returns (can be value or percentage)
            labels: optional date labels for exceedance tracking
        """
        if not returns:
            return HistoricalVaRResult()

        data = returns[-self._window:] if len(returns) > self._window else returns[:]
        n = len(data)
        sorted_data = sorted(data)

        # statistics
        mean_r = sum(data) / n
        variance = sum((r - mean_r) ** 2 for r in data) / (n - 1) if n > 1 else 0.0
        std_r = variance ** 0.5 if variance > 0 else 0.0
        skew = 0.0
        kurt = 0.0
        if std_r > 0:
            skew = sum(((r - mean_r) / std_r) ** 3 for r in data) / n
            kurt = sum(((r - mean_r) / std_r) ** 4 for r in data) / n - 3

        # exceedance counts
        exceed_95 = sum(1 for r in data if r < -sorted_data[int(n * 0.05)])
        exceed_99 = sum(1 for r in data if r < -sorted_data[int(n * 0.01)])

        # worst 5 losses
        worst_5 = sorted_data[:5]

        return HistoricalVaRResult(
            var_95=abs(sorted_data[max(0, int(n * 0.05))]),
            var_99=abs(sorted_data[max(0, int(n * 0.01))]),
            var_995=abs(sorted_data[max(0, int(n * 0.005))]),
            var_999=abs(sorted_data[max(0, int(n * 0.001))]),
            min_return=sorted_data[0],
            max_return=sorted_data[-1],
            mean_return=mean_r,
            std_return=std_r,
            skewness=skew,
            kurtosis=kurt,
            sample_size=n,
            window_days=self._window,
            exceedance_ratio_95=exceed_95 / max(n, 1),
            exceedance_ratio_99=exceed_99 / max(n, 1),
            worst_5_losses=worst_5,
        )

    def compute_rolling(
        self,
        returns: List[float],
        window: Optional[int] = None,
    ) -> List[HistoricalVaRResult]:
        """Compute rolling historical VaR series.

        Args:
            returns: full return history
            window: rolling window size (defaults to self._window)
        """
        w = window or self._window
        results = []
        for i in range(w, len(returns) + 1):
            window_data = returns[i - w:i]
            results.append(self.compute(window_data))
        return results
