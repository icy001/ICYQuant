"""Quantile Analysis — stratified factor performance analysis.

Supports::

    Top 5%, Top 10%, Quintile, Decile

Used for group return analysis and factor monotonicity evaluation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class QuantileMethod(str, Enum):
    """Quantile grouping methods."""

    TOP_PCT = "top_pct"       # Top N% (e.g., top 5%, top 10%)
    QUINTILE = "quintile"     # 5 equal groups
    DECILE = "decile"         # 10 equal groups
    CUSTOM = "custom"         # Custom breakpoints


@dataclass
class QuantileGroup:
    """A single quantile group result."""

    group_id: int
    label: str
    count: int
    mean_factor: float = 0.0
    mean_return: float = 0.0
    cumulative_return: float = 0.0
    hit_rate: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class QuantileAnalyzer:
    """Stratified factor performance analysis.

    Groups assets by factor value into quantiles and computes
    performance statistics for each group, enabling:
    * Monotonicity assessment (top vs bottom performance)
    * Spread analysis (long-short return)
    * Hit rate by quantile
    """

    def __init__(
        self,
        method: QuantileMethod = QuantileMethod.QUINTILE,
        n_groups: int = 5,
    ) -> None:
        self._method = method
        self._n_groups = n_groups

    @property
    def method(self) -> QuantileMethod:
        return self._method

    def analyze(
        self,
        factor_values: List[float],
        forward_returns: List[float],
        identifiers: Optional[List[str]] = None,
    ) -> List[QuantileGroup]:
        """Perform quantile analysis.

        Args:
            factor_values: factor values at time t
            forward_returns: forward returns from t to t+1
            identifiers: optional asset identifiers

        Returns:
            list of QuantileGroup results
        """
        if not factor_values or not forward_returns:
            return []

        n = min(len(factor_values), len(forward_returns))
        paired = list(zip(factor_values[:n], forward_returns[:n]))

        # Sort by factor value (ascending)
        paired.sort(key=lambda x: x[0])

        n_groups = self._resolve_n_groups(n)
        group_size = n // n_groups
        remainder = n % n_groups

        groups: List[QuantileGroup] = []
        start = 0

        for g in range(n_groups):
            size = group_size + (1 if g < remainder else 0)
            end = start + size
            group_data = paired[start:end]

            if not group_data:
                break

            factor_vals = [f for f, _ in group_data]
            return_vals = [r for _, r in group_data]

            mean_factor = sum(factor_vals) / len(factor_vals)
            mean_return = sum(return_vals) / len(return_vals)
            hit_rate = sum(1 for r in return_vals if r > 0) / len(return_vals)

            # Cumulative return (simple sum for cross-section)
            cum_return = sum(return_vals)

            # Sharpe (approximate for cross-section)
            mean_r = mean_return
            variance = sum((r - mean_r) ** 2 for r in return_vals) / len(return_vals)
            sharpe = mean_r / (variance ** 0.5) if variance > 0 else 0.0

            # Simple max drawdown
            running_min = 0.0
            running = 0.0
            max_dd = 0.0
            for r in return_vals:
                running += r
                running_min = min(running_min, running)
                max_dd = min(max_dd, running - running_min)

            group = QuantileGroup(
                group_id=g + 1,
                label=self._group_label(g, n_groups),
                count=size,
                mean_factor=mean_factor,
                mean_return=mean_return,
                cumulative_return=cum_return,
                hit_rate=hit_rate,
                sharpe=sharpe,
                max_drawdown=abs(max_dd),
            )
            groups.append(group)
            start = end

        return groups

    def _resolve_n_groups(self, n_assets: int) -> int:
        if self._method == QuantileMethod.TOP_PCT:
            return max(1, int(1 / (self._n_groups / 100)))
        elif self._method == QuantileMethod.QUINTILE:
            return min(5, n_assets)
        elif self._method == QuantileMethod.DECILE:
            return min(10, n_assets)
        else:
            return min(self._n_groups, n_assets)

    def _group_label(self, group_idx: int, n_groups: int) -> str:
        if self._method == QuantileMethod.QUINTILE:
            labels = ["Q1 (Low)", "Q2", "Q3", "Q4", "Q5 (High)"]
            return labels[group_idx] if group_idx < len(labels) else f"Q{group_idx + 1}"
        elif self._method == QuantileMethod.DECILE:
            labels = [
                "D1 (Low)", "D2", "D3", "D4", "D5",
                "D6", "D7", "D8", "D9", "D10 (High)",
            ]
            return labels[group_idx] if group_idx < len(labels) else f"D{group_idx + 1}"
        elif self._method == QuantileMethod.TOP_PCT:
            if group_idx == 0:
                return f"Top {self._n_groups}%"
            else:
                return f"Bottom {100 - self._n_groups}%"
        return f"Group {group_idx + 1}"

    def spread_analysis(
        self, groups: List[QuantileGroup]
    ) -> Dict[str, Any]:
        """Compute top vs bottom spread metrics."""
        if len(groups) < 2:
            return {}

        top = groups[-1]
        bottom = groups[0]

        return {
            "spread_return": top.mean_return - bottom.mean_return,
            "spread_hit_rate": top.hit_rate - bottom.hit_rate,
            "spread_sharpe": top.sharpe - bottom.sharpe,
            "top_mean_return": top.mean_return,
            "bottom_mean_return": bottom.mean_return,
            "monotonic": all(
                groups[i].mean_return <= groups[i + 1].mean_return
                for i in range(len(groups) - 1)
            ),
        }

    def to_dict(
        self, groups: List[QuantileGroup]
    ) -> List[Dict[str, Any]]:
        """Convert groups to serializable dicts."""
        return [
            {
                "group_id": g.group_id,
                "label": g.label,
                "count": g.count,
                "mean_factor": g.mean_factor,
                "mean_return": g.mean_return,
                "cumulative_return": g.cumulative_return,
                "hit_rate": g.hit_rate,
                "sharpe": g.sharpe,
                "max_drawdown": g.max_drawdown,
            }
            for g in groups
        ]
