"""Turnover Analysis — portfolio turnover and signal stability.

Statistics::

    Holding Turnover, Signal Stability, Holding Persistence

Evaluates transaction cost impact of factor-based strategies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TurnoverResult:
    """Turnover analysis result."""

    factor_name: str = ""
    avg_turnover: float = 0.0
    turnover_std: float = 0.0
    signal_autocorrelation: float = 0.0
    signal_stability: float = 0.0
    holding_persistence: float = 0.0
    daily_turnover: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "factor_name": self.factor_name,
            "avg_turnover": self.avg_turnover,
            "turnover_std": self.turnover_std,
            "signal_autocorrelation": self.signal_autocorrelation,
            "signal_stability": self.signal_stability,
            "holding_persistence": self.holding_persistence,
            "daily_turnover_count": len(self.daily_turnover),
            "metadata": self.metadata,
        }


class TurnoverAnalyzer:
    """Portfolio turnover and signal stability analyzer.

    Measures:
    * Holding turnover: how much the portfolio composition changes
    * Signal autocorrelation: persistence of factor values
    * Holding persistence: overlap of top holdings across periods
    """

    def __init__(
        self,
        top_n: int = 50,
        min_periods: int = 20,
    ) -> None:
        self._top_n = top_n
        self._min_periods = min_periods

    def analyze(
        self,
        factor_panel: Dict[str, List[float]],
        identifiers_panel: Optional[Dict[str, List[str]]] = None,
        factor_name: str = "",
    ) -> TurnoverResult:
        """Analyze factor turnover.

        Args:
            factor_panel: date → factor values
            identifiers_panel: date → asset identifiers
            factor_name: factor identifier

        Returns:
            TurnoverResult with turnover metrics
        """
        dates = sorted(factor_panel.keys())
        if len(dates) < 2:
            return TurnoverResult(factor_name=factor_name)

        daily_turnover: List[float] = []
        signal_autocorrs: List[float] = []

        prev_top_ids: Optional[set] = None

        for i in range(1, len(dates)):
            prev_date = dates[i - 1]
            curr_date = dates[i]

            prev_vals = factor_panel.get(prev_date, [])
            curr_vals = factor_panel.get(curr_date, [])

            if not prev_vals or not curr_vals:
                continue

            # Signal autocorrelation
            n = min(len(prev_vals), len(curr_vals))
            if n >= self._min_periods:
                mean_p = sum(prev_vals[:n]) / n
                mean_c = sum(curr_vals[:n]) / n
                cov = sum(
                    (p - mean_p) * (c - mean_c)
                    for p, c in zip(prev_vals[:n], curr_vals[:n])
                )
                var_p = sum((p - mean_p) ** 2 for p in prev_vals[:n])
                var_c = sum((c - mean_c) ** 2 for c in curr_vals[:n])
                if var_p > 0 and var_c > 0:
                    autocorr = cov / ((var_p * var_c) ** 0.5)
                    signal_autocorrs.append(autocorr)

            # Top-N holding turnover
            if identifiers_panel:
                prev_ids = identifiers_panel.get(prev_date, [])
                curr_ids = identifiers_panel.get(curr_date, [])

                if prev_ids and curr_ids:
                    # Get top N by factor value for each period
                    prev_paired = sorted(
                        zip(prev_ids, prev_vals),
                        key=lambda x: x[1],
                        reverse=True,
                    )
                    curr_paired = sorted(
                        zip(curr_ids, curr_vals),
                        key=lambda x: x[1],
                        reverse=True,
                    )

                    n_top = min(self._top_n, len(prev_paired), len(curr_paired))
                    prev_top = {pid for pid, _ in prev_paired[:n_top]}
                    curr_top = {pid for pid, _ in curr_paired[:n_top]}

                    overlap = len(prev_top & curr_top)
                    turnover_rate = 1.0 - (overlap / n_top) if n_top > 0 else 0.0
                    daily_turnover.append(turnover_rate)
            else:
                # Without identifiers, use rank-based turnover
                prev_paired = sorted(enumerate(prev_vals), key=lambda x: x[1], reverse=True)
                curr_paired = sorted(enumerate(curr_vals), key=lambda x: x[1], reverse=True)

                n_top = min(self._top_n, len(prev_paired), len(curr_paired))
                prev_top_idx = {idx for idx, _ in prev_paired[:n_top]}
                curr_top_idx = {idx for idx, _ in curr_paired[:n_top]}

                overlap = len(prev_top_idx & curr_top_idx)
                turnover_rate = 1.0 - (overlap / n_top) if n_top > 0 else 0.0
                daily_turnover.append(turnover_rate)

        # Compute summary statistics
        if daily_turnover:
            avg_turnover = sum(daily_turnover) / len(daily_turnover)
            variance = sum((t - avg_turnover) ** 2 for t in daily_turnover) / len(daily_turnover)
            turnover_std = variance ** 0.5
            holding_persistence = 1.0 - avg_turnover
        else:
            avg_turnover = 0.0
            turnover_std = 0.0
            holding_persistence = 0.0

        if signal_autocorrs:
            signal_autocorrelation = sum(signal_autocorrs) / len(signal_autocorrs)
        else:
            signal_autocorrelation = 0.0

        # Signal stability: how stable is the factor ranking
        signal_stability = signal_autocorrelation

        return TurnoverResult(
            factor_name=factor_name,
            avg_turnover=avg_turnover,
            turnover_std=turnover_std,
            signal_autocorrelation=signal_autocorrelation,
            signal_stability=signal_stability,
            holding_persistence=holding_persistence,
            daily_turnover=daily_turnover,
        )
