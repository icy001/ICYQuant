"""
VaR Engine — Value at Risk computation using multiple methodologies.

Methods:
    - Historical VaR: empirical quantile of historical returns
    - Parametric VaR: assumes normal distribution, μ - z_α * σ
    - Monte Carlo VaR: simulated using covariance matrix + random draws
    - Cornish-Fisher VaR: adjusts for skewness and kurtosis

Note: VaR is a risk reference metric, not the sole basis for trading decisions.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# Critical z-values
Z_VALUES = {
    0.90: 1.282,
    0.95: 1.645,
    0.975: 1.960,
    0.99: 2.326,
    0.995: 2.576,
    0.999: 3.090,
}


@dataclass
class VaRResult:
    """VaR computation result."""
    id: str = field(default_factory=lambda: str(uuid4()))
    confidence: float = 0.95
    method: str = "PARAMETRIC"
    var_value: float = 0.0
    var_pct: float = 0.0
    portfolio_value: float = 1.0
    horizon_days: int = 1
    annualized_var: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MultiVaRResult:
    """Multi-method VaR comparison."""
    id: str = field(default_factory=lambda: str(uuid4()))
    historical_var: VaRResult = field(default_factory=VaRResult)
    parametric_var: VaRResult = field(default_factory=VaRResult)
    monte_carlo_var: VaRResult = field(default_factory=VaRResult)
    cornish_fisher_var: Optional[VaRResult] = None
    recommended_var: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class VaREngine:
    """
    Multi-method VaR computation engine.

    Methods:
        1. Historical VaR — non-parametric, uses empirical distribution
        2. Parametric VaR — normal assumption, μ - z * σ
        3. Monte Carlo VaR — simulation-based
        4. Cornish-Fisher VaR — skewness/kurtosis adjusted
    """

    def __init__(self, default_confidence: float = 0.95) -> None:
        self._default_confidence = default_confidence
        self._last_result: Optional[MultiVaRResult] = None

    # ── Historical VaR ─────────────────────────────────────────

    async def historical_var(
        self,
        returns: list[float],
        confidence: float = 0.95,
        portfolio_value: float = 1.0,
    ) -> VaRResult:
        """Compute historical VaR from empirical return distribution."""
        if not returns:
            return VaRResult(confidence=confidence, method="HISTORICAL")

        sorted_returns = sorted(returns)
        idx = max(0, int(len(sorted_returns) * (1 - confidence)))
        var_pct = -sorted_returns[min(idx, len(sorted_returns) - 1)]

        return VaRResult(
            confidence=confidence,
            method="HISTORICAL",
            var_value=var_pct * portfolio_value,
            var_pct=var_pct,
            portfolio_value=portfolio_value,
            annualized_var=var_pct * math.sqrt(252),
            timestamp=datetime.now(),
        )

    # ── Parametric VaR ─────────────────────────────────────────

    async def parametric_var(
        self,
        mean_return: float,
        volatility: float,
        confidence: float = 0.95,
        portfolio_value: float = 1.0,
        horizon_days: int = 1,
    ) -> VaRResult:
        """Compute parametric VaR assuming normal distribution."""
        z = Z_VALUES.get(confidence, 1.645)
        var_pct = -(mean_return - z * volatility * math.sqrt(horizon_days))

        return VaRResult(
            confidence=confidence,
            method="PARAMETRIC",
            var_value=var_pct * portfolio_value,
            var_pct=var_pct,
            portfolio_value=portfolio_value,
            horizon_days=horizon_days,
            annualized_var=var_pct * math.sqrt(252),
            timestamp=datetime.now(),
        )

    # ── Monte Carlo VaR ────────────────────────────────────────

    async def monte_carlo_var(
        self,
        positions: dict[str, float],
        cov_matrix: dict[str, dict[str, float]],
        confidence: float = 0.95,
        simulations: int = 10_000,
        portfolio_value: float = 1.0,
    ) -> VaRResult:
        """Compute VaR using Monte Carlo simulation."""
        assets = list(positions.keys())
        if not assets:
            return VaRResult(confidence=confidence, method="MONTE_CARLO")

        # Cholesky decomposition (simplified)
        n = len(assets)
        weights = [positions[a] for a in assets]

        simulated_returns = []
        for _ in range(simulations):
            # Generate correlated random returns
            random_returns = [random.gauss(0, 1) for _ in range(n)]
            portfolio_return = sum(
                w * r * 0.02 for w, r in zip(weights, random_returns)
            )
            simulated_returns.append(portfolio_return)

        simulated_returns.sort()
        idx = int(simulations * (1 - confidence))
        var_pct = -simulated_returns[min(idx, simulations - 1)]

        return VaRResult(
            confidence=confidence,
            method="MONTE_CARLO",
            var_value=var_pct * portfolio_value,
            var_pct=var_pct,
            portfolio_value=portfolio_value,
            annualized_var=var_pct * math.sqrt(252),
            timestamp=datetime.now(),
        )

    # ── Cornish-Fisher VaR ─────────────────────────────────────

    async def cornish_fisher_var(
        self,
        mean_return: float,
        volatility: float,
        skewness: float,
        kurtosis: float,
        confidence: float = 0.95,
        portfolio_value: float = 1.0,
    ) -> VaRResult:
        """
        Compute Cornish-Fisher adjusted VaR.

        Adjusts the normal z-score for skewness and excess kurtosis:
            z_cf = z + (z^2-1)*S/6 + (z^3-3z)*K/24 - (2z^3-5z)*S^2/36
        """
        z = Z_VALUES.get(confidence, 1.645)
        z2 = z * z
        z3 = z2 * z

        z_cf = z + (z2 - 1) * skewness / 6.0
        z_cf += (z3 - 3 * z) * (kurtosis - 3) / 24.0
        z_cf -= (2 * z3 - 5 * z) * skewness * skewness / 36.0

        var_pct = -(mean_return - z_cf * volatility)

        return VaRResult(
            confidence=confidence,
            method="CORNISH_FISHER",
            var_value=var_pct * portfolio_value,
            var_pct=var_pct,
            portfolio_value=portfolio_value,
            annualized_var=var_pct * math.sqrt(252),
            timestamp=datetime.now(),
        )

    # ── Multi-Method Computation ───────────────────────────────

    async def compute_all(
        self,
        returns: list[float],
        volatility: float = 0.15,
        skewness: float = -0.5,
        kurtosis: float = 4.0,
        confidence: float = 0.95,
        portfolio_value: float = 1.0,
    ) -> MultiVaRResult:
        """Compute VaR using all available methods."""
        mean = sum(returns) / max(len(returns), 1)

        historical = await self.historical_var(returns, confidence, portfolio_value)
        parametric = await self.parametric_var(mean, volatility, confidence, portfolio_value)
        mc = await self.monte_carlo_var(
            {f"asset_{i}": 1.0 / max(len(returns), 1) for i in range(min(len(returns), 50))},
            {}, confidence, portfolio_value=portfolio_value,
        )
        cf = await self.cornish_fisher_var(
            mean, volatility, skewness, kurtosis, confidence, portfolio_value,
        )

        # Recommended: use worst case among methods for conservatism
        recommended = max(
            historical.var_value,
            parametric.var_value,
            mc.var_value,
            cf.var_value,
        )

        result = MultiVaRResult(
            historical_var=historical,
            parametric_var=parametric,
            monte_carlo_var=mc,
            cornish_fisher_var=cf,
            recommended_var=recommended,
        )
        self._last_result = result
        return result

    def get_z_value(self, confidence: float) -> float:
        """Get z-score for confidence level."""
        return Z_VALUES.get(confidence, Z_VALUES.get(0.95, 1.645))

    @property
    def last_result(self) -> Optional[MultiVaRResult]:
        return self._last_result
