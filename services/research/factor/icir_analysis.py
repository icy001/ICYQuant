"""ICIR Analysis — Information Coefficient / Std(IC) ratio.

Computes::

    Mean IC / Std(IC)

Evaluates factor stability — higher ICIR means more consistent predictive power.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class IciRResult:
    """ICIR analysis result."""

    factor_name: str = ""
    icir: float = 0.0
    mean_ic: float = 0.0
    std_ic: float = 0.0
    rank_icir: float = 0.0
    mean_rankic: float = 0.0
    std_rankic: float = 0.0
    rolling_icir: Optional[List[float]] = None
    t_statistic: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "factor_name": self.factor_name,
            "icir": self.icir,
            "mean_ic": self.mean_ic,
            "std_ic": self.std_ic,
            "rank_icir": self.rank_icir,
            "mean_rankic": self.mean_rankic,
            "std_rankic": self.std_rankic,
            "t_statistic": self.t_statistic,
            "metadata": self.metadata,
        }


class IciRAnalyzer:
    """Information Coefficient Information Ratio analyzer.

    ICIR = Mean(IC) / Std(IC)

    Interpretation:
    * ICIR > 0.5: Excellent
    * ICIR 0.3-0.5: Good
    * ICIR 0.1-0.3: Acceptable
    * ICIR < 0.1: Weak
    """

    def __init__(self) -> None:
        self._thresholds = {
            "excellent": 0.5,
            "good": 0.3,
            "acceptable": 0.1,
        }

    def compute(
        self,
        daily_ic: List[float],
        daily_rankic: Optional[List[float]] = None,
        factor_name: str = "",
        rolling_window: int = 60,
    ) -> IciRResult:
        """Compute ICIR from daily IC series.

        Args:
            daily_ic: daily IC values
            daily_rankic: daily RankIC values (optional)
            factor_name: factor identifier
            rolling_window: window for rolling ICIR

        Returns:
            IciRResult with ICIR and analysis
        """
        if not daily_ic:
            return IciRResult(factor_name=factor_name)

        n = len(daily_ic)
        mean_ic = sum(daily_ic) / n
        variance = sum((ic - mean_ic) ** 2 for ic in daily_ic) / n
        std_ic = variance ** 0.5
        icir = mean_ic / std_ic if std_ic > 0 else 0.0

        # T-statistic: mean_ic / (std_ic / sqrt(n))
        t_stat = mean_ic / (std_ic / (n ** 0.5)) if std_ic > 0 else 0.0

        # Rank ICIR
        rank_icir = 0.0
        mean_rankic = 0.0
        std_rankic = 0.0
        if daily_rankic:
            nr = len(daily_rankic)
            mean_rankic = sum(daily_rankic) / nr
            var_rankic = sum((ric - mean_rankic) ** 2 for ric in daily_rankic) / nr
            std_rankic = var_rankic ** 0.5
            rank_icir = mean_rankic / std_rankic if std_rankic > 0 else 0.0

        # Rolling ICIR
        rolling_icir: List[float] = []
        if n >= rolling_window:
            for i in range(rolling_window - 1, n):
                window = daily_ic[i - rolling_window + 1 : i + 1]
                w_mean = sum(window) / rolling_window
                w_var = sum((ic - w_mean) ** 2 for ic in window) / rolling_window
                w_std = w_var ** 0.5
                w_icir = w_mean / w_std if w_std > 0 else 0.0
                rolling_icir.append(w_icir)

        # Quality assessment
        quality = "weak"
        if icir >= self._thresholds["excellent"]:
            quality = "excellent"
        elif icir >= self._thresholds["good"]:
            quality = "good"
        elif icir >= self._thresholds["acceptable"]:
            quality = "acceptable"

        return IciRResult(
            factor_name=factor_name,
            icir=icir,
            mean_ic=mean_ic,
            std_ic=std_ic,
            rank_icir=rank_icir,
            mean_rankic=mean_rankic,
            std_rankic=std_rankic,
            rolling_icir=rolling_icir,
            t_statistic=t_stat,
            metadata={
                "quality": quality,
                "n_periods": n,
                "thresholds": self._thresholds,
            },
        )

    def quality(self, icir: float) -> str:
        """Assess ICIR quality."""
        if icir >= self._thresholds["excellent"]:
            return "excellent"
        elif icir >= self._thresholds["good"]:
            return "good"
        elif icir >= self._thresholds["acceptable"]:
            return "acceptable"
        return "weak"
