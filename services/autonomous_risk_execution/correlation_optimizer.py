"""
Correlation Optimizer — reduce portfolio correlation clustering.

Prevents the portfolio from becoming a cluster of highly correlated
positions, even when each individual position looks good in isolation.

Key insight:
    Strategy Diversification ≠ Risk Diversification
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class CorrelationConfig:
    """Correlation optimization configuration."""
    max_pairwise_correlation: float = 0.70
    max_avg_correlation: float = 0.50
    correlation_penalty_strength: float = 0.30
    min_diversification_ratio: float = 0.30


@dataclass
class CorrelationResult:
    """Result of correlation optimization."""
    id: str = field(default_factory=lambda: str(uuid4()))
    avg_correlation: float = 0.0
    max_correlation: float = 0.0
    correlation_matrix: dict[str, dict[str, float]] = field(default_factory=dict)
    high_corr_pairs: list[dict] = field(default_factory=list)
    diversification_ratio: float = 1.0
    adjusted_weights: dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class CorrelationOptimizer:
    """
    Correlation-aware position optimization.

    When two positions are highly correlated (e.g. 0.91), the system
    prefers reducing one rather than keeping both at full weight,
    even if both have high individual Sharpe ratios.

    Formula:
        weight_i_adjusted = weight_i * (1 - corr_penalty * max_corr_to_others_i)
    """

    def __init__(self, config: Optional[CorrelationConfig] = None) -> None:
        self._config = config or CorrelationConfig()
        self._last_result: Optional[CorrelationResult] = None

    async def optimize(
        self,
        positions: dict[str, float],
        correlation_matrix: dict[str, dict[str, float]],
    ) -> CorrelationResult:
        """Apply correlation-based position adjustments."""
        result = CorrelationResult(correlation_matrix=correlation_matrix)

        if not correlation_matrix or not positions:
            result.adjusted_weights = dict(positions)
            return result

        # Compute average and max correlations
        all_corrs = []
        high_corr_pairs = []
        seen = set()

        for a in correlation_matrix:
            for b, corr in correlation_matrix[a].items():
                if a >= b or (a, b) in seen or (b, a) in seen:
                    continue
                seen.add((a, b))
                all_corrs.append(abs(corr))
                if abs(corr) > self._config.max_pairwise_correlation:
                    high_corr_pairs.append({
                        "pair": (a, b), "correlation": corr,
                        "penalty": abs(corr) - self._config.max_pairwise_correlation,
                    })

        result.avg_correlation = sum(all_corrs) / max(len(all_corrs), 1)
        result.max_correlation = max(all_corrs) if all_corrs else 0
        result.high_corr_pairs = high_corr_pairs

        # Adjust weights based on pairwise correlations
        adjusted = dict(positions)
        max_corrs = self._compute_max_correlations(positions, correlation_matrix)

        for asset, weight in adjusted.items():
            max_corr = max_corrs.get(asset, 0)
            if max_corr > self._config.max_pairwise_correlation:
                excess = max_corr - self._config.max_pairwise_correlation
                penalty = 1.0 - self._config.correlation_penalty_strength * excess
                adjusted[asset] = weight * max(penalty, self._config.min_diversification_ratio)

        # Renormalize
        total_orig = sum(abs(v) for v in positions.values()) or 1.0
        total_adj = sum(abs(v) for v in adjusted.values()) or 1.0
        adjusted = {k: v * (total_orig / total_adj) for k, v in adjusted.items()}

        result.adjusted_weights = adjusted
        result.diversification_ratio = (
            sum(v * v for v in adjusted.values()) / max(len(adjusted), 1)
        )
        result.timestamp = datetime.now()
        self._last_result = result

        if high_corr_pairs:
            logger.info("Correlation opt: %d high-corr pairs, avg=%.3f",
                        len(high_corr_pairs), result.avg_correlation)
        return result

    def _compute_max_correlations(
        self,
        positions: dict[str, float],
        corr_matrix: dict[str, dict[str, float]],
    ) -> dict[str, float]:
        """Find maximum correlation for each position."""
        max_corrs: dict[str, float] = {}
        assets = list(positions.keys())
        for asset in assets:
            max_corr = 0.0
            for other in assets:
                if other == asset:
                    continue
                corr = corr_matrix.get(asset, {}).get(other, 0)
                max_corr = max(max_corr, abs(corr))
            max_corrs[asset] = max_corr
        return max_corrs

    def compute_diversification_ratio(self, weights: dict[str, float]) -> float:
        """DR = (sum w_i * vol_i)^2 / sum (w_i * vol_i)^2"""
        squared_sum = sum(w * w for w in weights.values())
        total = sum(abs(w) for w in weights.values())
        if squared_sum <= 0:
            return 0.0
        return (total * total) / squared_sum / max(len(weights), 1)

    @property
    def last_result(self) -> Optional[CorrelationResult]:
        return self._last_result
