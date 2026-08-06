"""IC Analysis — Information Coefficient for factor predictive power.

Outputs::

    Daily IC, Rolling IC, Mean IC, IC Distribution

Evaluates how well factor values predict forward returns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ICResult:
    """Information Coefficient analysis result."""

    factor_name: str = ""
    mean_ic: float = 0.0
    std_ic: float = 0.0
    ic_ir: float = 0.0
    ic_positive_ratio: float = 0.0
    daily_ic: List[float] = field(default_factory=list)
    rolling_ic: Optional[List[float]] = None
    ic_distribution: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "factor_name": self.factor_name,
            "mean_ic": self.mean_ic,
            "std_ic": self.std_ic,
            "ic_ir": self.ic_ir,
            "ic_positive_ratio": self.ic_positive_ratio,
            "daily_ic_count": len(self.daily_ic),
            "ic_distribution": self.ic_distribution,
            "metadata": self.metadata,
        }


class ICAnalyzer:
    """Information Coefficient analyzer.

    Computes Pearson correlation between factor values at time t
    and forward returns at time t+1, measuring linear predictive power.
    """

    def __init__(self, min_periods: int = 20) -> None:
        self._min_periods = min_periods

    def compute(
        self,
        factor_values: List[float],
        forward_returns: List[float],
        factor_name: str = "",
    ) -> ICResult:
        """Compute single-period IC.

        Args:
            factor_values: factor values at time t
            forward_returns: forward returns at time t+1
            factor_name: factor identifier

        Returns:
            ICResult with mean IC, std IC, etc.
        """
        if not factor_values or not forward_returns:
            return ICResult(factor_name=factor_name)

        n = min(len(factor_values), len(forward_returns))

        # Pearson correlation
        mean_f = sum(factor_values[:n]) / n
        mean_r = sum(forward_returns[:n]) / n

        cov = sum(
            (f - mean_f) * (r - mean_r)
            for f, r in zip(factor_values[:n], forward_returns[:n])
        )
        var_f = sum((f - mean_f) ** 2 for f in factor_values[:n])
        var_r = sum((r - mean_r) ** 2 for r in forward_returns[:n])

        if var_f == 0 or var_r == 0:
            ic = 0.0
        else:
            ic = cov / ((var_f * var_r) ** 0.5)

        return ICResult(
            factor_name=factor_name,
            mean_ic=ic,
            std_ic=0.0,  # single period has no std
            ic_ir=0.0,
            ic_positive_ratio=1.0 if ic > 0 else 0.0,
            daily_ic=[ic],
        )

    def compute_time_series(
        self,
        factor_panel: Dict[str, List[float]],
        forward_returns_panel: Dict[str, List[float]],
        factor_name: str = "",
        rolling_window: int = 20,
    ) -> ICResult:
        """Compute IC time series across multiple periods.

        Args:
            factor_panel: date → factor values
            forward_returns_panel: date → forward returns
            factor_name: factor identifier
            rolling_window: window size for rolling IC

        Returns:
            ICResult with full time series analysis
        """
        dates = sorted(set(factor_panel.keys()) & set(forward_returns_panel.keys()))
        if not dates:
            return ICResult(factor_name=factor_name)

        daily_ic: List[float] = []

        for date in dates:
            f_vals = factor_panel.get(date, [])
            r_vals = forward_returns_panel.get(date, [])
            if not f_vals or not r_vals:
                continue

            n = min(len(f_vals), len(r_vals))
            if n < self._min_periods:
                continue

            mean_f = sum(f_vals[:n]) / n
            mean_r = sum(r_vals[:n]) / n

            cov = sum((f - mean_f) * (r - mean_r) for f, r in zip(f_vals[:n], r_vals[:n]))
            var_f = sum((f - mean_f) ** 2 for f in f_vals[:n])
            var_r = sum((r - mean_r) ** 2 for r in r_vals[:n])

            if var_f > 0 and var_r > 0:
                ic = cov / ((var_f * var_r) ** 0.5)
                daily_ic.append(ic)

        if not daily_ic:
            return ICResult(factor_name=factor_name)

        n_ic = len(daily_ic)
        mean_ic = sum(daily_ic) / n_ic
        variance = sum((ic - mean_ic) ** 2 for ic in daily_ic) / n_ic
        std_ic = variance ** 0.5
        ic_ir = mean_ic / std_ic if std_ic > 0 else 0.0
        positive_ratio = sum(1 for ic in daily_ic if ic > 0) / n_ic

        # Rolling IC
        rolling_ic: List[float] = []
        if n_ic >= rolling_window:
            for i in range(rolling_window - 1, n_ic):
                window = daily_ic[i - rolling_window + 1 : i + 1]
                rolling_ic.append(sum(window) / rolling_window)

        # IC distribution
        sorted_ic = sorted(daily_ic)
        ic_distribution = {
            "count": n_ic,
            "min": sorted_ic[0],
            "max": sorted_ic[-1],
            "median": sorted_ic[n_ic // 2],
            "q25": sorted_ic[n_ic // 4],
            "q75": sorted_ic[(3 * n_ic) // 4],
            "skew": sum((ic - mean_ic) ** 3 for ic in daily_ic) / (n_ic * std_ic ** 3) if std_ic > 0 else 0.0,
        }

        return ICResult(
            factor_name=factor_name,
            mean_ic=mean_ic,
            std_ic=std_ic,
            ic_ir=ic_ir,
            ic_positive_ratio=positive_ratio,
            daily_ic=daily_ic,
            rolling_ic=rolling_ic,
            ic_distribution=ic_distribution,
        )
