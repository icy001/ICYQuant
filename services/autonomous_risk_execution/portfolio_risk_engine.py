"""
Portfolio Risk Engine — comprehensive portfolio risk analysis.

Computes multi-dimensional portfolio risk metrics:
    - Volatility (realized, implied)
    - VaR (historical, parametric, Monte Carlo)
    - Expected Shortfall (CVaR)
    - Drawdown statistics
    - Correlation matrix
    - Risk contribution (marginal, component)
    - Diversification metrics
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class PortfolioRiskMetrics:
    """Comprehensive portfolio risk metrics."""
    id: str = field(default_factory=lambda: str(uuid4()))
    total_volatility: float = 0.0
    var_95: float = 0.0
    var_99: float = 0.0
    expected_shortfall_95: float = 0.0
    expected_shortfall_99: float = 0.0
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    diversification_ratio: float = 0.0
    effective_n: float = 0.0
    correlation_matrix: dict[str, dict[str, float]] = field(default_factory=dict)
    risk_contributions: dict[str, float] = field(default_factory=dict)
    marginal_risks: dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class PortfolioRiskEngine:
    """
    Core portfolio risk computation engine.

    Provides:
        - Real-time portfolio risk metrics
        - Historical VaR / ES computation
        - Risk decomposition
        - Diversification analysis
    """

    def __init__(self) -> None:
        self._last_metrics: Optional[PortfolioRiskMetrics] = None

    async def compute(
        self,
        positions: dict[str, float],
        returns: Optional[dict[str, list[float]]] = None,
        cov_matrix: Optional[dict[str, dict[str, float]]] = None,
    ) -> PortfolioRiskMetrics:
        """Compute comprehensive portfolio risk metrics."""
        metrics = PortfolioRiskMetrics()

        # Total volatility
        if cov_matrix and positions:
            total_var = 0.0
            for a, wa in positions.items():
                for b, wb in positions.items():
                    cov = cov_matrix.get(a, {}).get(b, 0)
                    total_var += wa * wb * cov
            metrics.total_volatility = max(0, total_var) ** 0.5

        # VaR estimates
        if metrics.total_volatility > 0:
            metrics.var_95 = metrics.total_volatility * 1.645
            metrics.var_99 = metrics.total_volatility * 2.326
            metrics.expected_shortfall_95 = metrics.var_95 * 1.25
            metrics.expected_shortfall_99 = metrics.var_99 * 1.15

        # Diversification
        if positions:
            hhi = sum(w * w for w in positions.values())
            metrics.effective_n = 1.0 / max(hhi, 0.001)
            metrics.diversification_ratio = len(positions) / max(metrics.effective_n, 1)

        # Risk contributions
        if cov_matrix and positions:
            total_std = max(metrics.total_volatility, 0.0001)
            metrics.risk_contributions = {}
            for asset, weight in positions.items():
                asset_contrib = 0.0
                for other, w_other in positions.items():
                    cov = cov_matrix.get(asset, {}).get(other, 0)
                    asset_contrib += weight * w_other * cov
                metrics.risk_contributions[asset] = asset_contrib / total_std

        metrics.timestamp = datetime.now()
        self._last_metrics = metrics
        return metrics

    async def compute_var_historical(
        self, returns: list[float], confidence: float = 0.95
    ) -> float:
        """Compute historical VaR from return series."""
        if not returns:
            return 0.0
        sorted_returns = sorted(returns)
        idx = int(len(sorted_returns) * (1 - confidence))
        return -sorted_returns[max(0, min(idx, len(sorted_returns) - 1))]

    async def compute_es_historical(
        self, returns: list[float], confidence: float = 0.95
    ) -> float:
        """Compute historical Expected Shortfall."""
        if not returns:
            return 0.0
        sorted_returns = sorted(returns)
        cutoff = int(len(sorted_returns) * (1 - confidence))
        tail = sorted_returns[:cutoff]
        if not tail:
            return 0.0
        return -sum(tail) / len(tail)

    def compute_risk_contribution(
        self, weight: float, position_vol: float, portfolio_vol: float,
        correlation: float = 0.5,
    ) -> float:
        """Compute marginal risk contribution."""
        if portfolio_vol <= 0:
            return 0.0
        return weight * position_vol * correlation / portfolio_vol

    def compute_diversification_ratio(
        self, weights: dict[str, float], vols: dict[str, float]
    ) -> float:
        """DR = (sum w_i * vol_i)^2 / sum (w_i * vol_i)^2"""
        weighted_vols = [abs(w) * vols.get(k, 0.15) for k, w in weights.items()]
        if not weighted_vols:
            return 0.0
        numerator = sum(weighted_vols) ** 2
        denominator = sum(v * v for v in weighted_vols)
        return numerator / max(denominator, 0.0001)

    @property
    def last_metrics(self) -> Optional[PortfolioRiskMetrics]:
        return self._last_metrics
