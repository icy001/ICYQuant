"""VaR Model — Value at Risk estimation for portfolio risk.

Supports methods:
* Historical — empirical quantile of historical returns
* Parametric — assumes normal distribution
* Monte Carlo — simulated returns
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VaRMethod(str, Enum):
    """VaR estimation methods."""

    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    MONTE_CARLO = "monte_carlo"


@dataclass
class VaRReport:
    """Value at Risk analysis report."""

    var_value: float = 0.0
    var_pct: float = 0.0
    confidence: float = 0.95
    method: VaRMethod = VaRMethod.HISTORICAL
    horizon_days: int = 1
    portfolio_value: float = 1.0
    worst_loss: float = 0.0
    expected_shortfall: float = 0.0  # beyond VaR
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "var_value": self.var_value,
            "var_pct": self.var_pct,
            "confidence": self.confidence,
            "method": self.method.value,
            "horizon_days": self.horizon_days,
            "portfolio_value": self.portfolio_value,
            "worst_loss": self.worst_loss,
            "expected_shortfall": self.expected_shortfall,
            "metadata": self.metadata,
        }


class VaRModel:
    """Value at Risk estimation.

    Computes VaR at specified confidence level using historical,
    parametric, or Monte Carlo methods.
    """

    def __init__(self) -> None:
        self._default_simulations: int = 10000

    async def compute(
        self,
        weights: Dict[str, float],
        confidence: float = 0.95,
        method: str = "historical",
        horizon_days: int = 1,
        portfolio_value: float = 1.0,
        returns_data: Optional[Dict[str, List[float]]] = None,
        cov_matrix: Optional[Dict[str, Dict[str, float]]] = None,
        **kwargs: Any,
    ) -> VaRReport:
        """Compute Value at Risk.

        Args:
            weights: Portfolio weights.
            confidence: Confidence level (e.g., 0.95, 0.99).
            method: 'historical', 'parametric', or 'monte_carlo'.
            horizon_days: VaR horizon in days.
            portfolio_value: Total portfolio value.
            returns_data: Historical returns per asset.
            cov_matrix: Covariance matrix.

        Returns:
            VaRReport with VaR estimate and diagnostics.
        """
        var_method = VaRMethod(method)

        if var_method == VaRMethod.HISTORICAL:
            return self._historical_var(
                weights, confidence, horizon_days,
                portfolio_value, returns_data,
            )
        elif var_method == VaRMethod.PARAMETRIC:
            return self._parametric_var(
                weights, confidence, horizon_days,
                portfolio_value, cov_matrix,
            )
        elif var_method == VaRMethod.MONTE_CARLO:
            return self._monte_carlo_var(
                weights, confidence, horizon_days,
                portfolio_value, returns_data, cov_matrix,
                kwargs.get("num_simulations", self._default_simulations),
            )
        else:
            return self._historical_var(
                weights, confidence, horizon_days,
                portfolio_value, returns_data,
            )

    def _historical_var(
        self,
        weights: Dict[str, float],
        confidence: float,
        horizon: int,
        portfolio_value: float,
        returns_data: Optional[Dict[str, List[float]]],
    ) -> VaRReport:
        """Historical simulation VaR."""
        if returns_data is None:
            returns_data = self._synthetic_returns(list(weights.keys()), 252)

        # Compute portfolio return series
        assets = list(weights.keys())
        T = min(len(returns_data.get(a, [])) for a in assets)
        portfolio_returns: List[float] = []
        worst_loss = 0.0

        for t in range(T):
            ret = sum(
                weights.get(a, 0.0) * returns_data.get(a, [])[t]
                for a in assets
            )
            portfolio_returns.append(ret)
            if ret < worst_loss:
                worst_loss = ret

        # Sort returns and find VaR at confidence level
        sorted_returns = sorted(portfolio_returns)
        var_idx = int((1.0 - confidence) * len(sorted_returns))
        var_ret = sorted_returns[var_idx] if var_idx < len(sorted_returns) else sorted_returns[0]

        # Scale to horizon (sqrt scaling)
        var_ret_scaled = var_ret * math.sqrt(horizon)
        var_value = abs(var_ret_scaled) * portfolio_value
        var_pct = abs(var_ret_scaled)

        # Expected shortfall (average of returns beyond VaR)
        tail = [r for r in sorted_returns if r <= var_ret]
        es = sum(tail) / len(tail) if tail else var_ret
        es_scaled = es * math.sqrt(horizon)

        return VaRReport(
            var_value=var_value,
            var_pct=var_pct,
            confidence=confidence,
            method=VaRMethod.HISTORICAL,
            horizon_days=horizon,
            portfolio_value=portfolio_value,
            worst_loss=abs(worst_loss) * portfolio_value,
            expected_shortfall=abs(es_scaled) * portfolio_value,
            metadata={"num_observations": T},
        )

    def _parametric_var(
        self,
        weights: Dict[str, float],
        confidence: float,
        horizon: int,
        portfolio_value: float,
        cov_matrix: Optional[Dict[str, Dict[str, float]]],
    ) -> VaRReport:
        """Parametric (variance-covariance) VaR.

        Assumes normally distributed returns.
        VaR = z_alpha * σ_p * sqrt(horizon) * V
        """
        if cov_matrix is None:
            cov_matrix = self._synthetic_cov(list(weights.keys()))

        # Portfolio variance
        assets = list(weights.keys())
        variance = 0.0
        for i in assets:
            for j in assets:
                variance += (
                    weights.get(i, 0.0)
                    * weights.get(j, 0.0)
                    * cov_matrix.get(i, {}).get(j, 0.0)
                )
        portfolio_vol = max(variance, 0.0) ** 0.5

        # Z-score for confidence level
        z_score = self._normal_quantile(confidence)

        # VaR
        var_ret = z_score * portfolio_vol * math.sqrt(horizon)
        var_value = abs(var_ret) * portfolio_value
        var_pct = abs(var_ret)

        # Expected shortfall for normal distribution
        phi_z = self._normal_pdf(z_score)
        es_ret = portfolio_vol * phi_z / (1.0 - confidence) * math.sqrt(horizon)
        es_value = es_ret * portfolio_value

        return VaRReport(
            var_value=var_value,
            var_pct=var_pct,
            confidence=confidence,
            method=VaRMethod.PARAMETRIC,
            horizon_days=horizon,
            portfolio_value=portfolio_value,
            worst_loss=var_value * 2.0,  # approximate
            expected_shortfall=es_value,
            metadata={
                "portfolio_volatility": portfolio_vol,
                "z_score": z_score,
            },
        )

    def _monte_carlo_var(
        self,
        weights: Dict[str, float],
        confidence: float,
        horizon: int,
        portfolio_value: float,
        returns_data: Optional[Dict[str, List[float]]],
        cov_matrix: Optional[Dict[str, Dict[str, float]]],
        num_simulations: int,
    ) -> VaRReport:
        """Monte Carlo simulation VaR."""
        if cov_matrix is None:
            cov_matrix = self._synthetic_cov(list(weights.keys()))

        assets = list(weights.keys())

        # Estimate mean and covariance from data
        if returns_data:
            means = {
                a: sum(returns_data[a]) / len(returns_data[a])
                for a in assets
            }
        else:
            means = {a: 0.0 for a in assets}

        # Cholesky decomposition (simplified: diagonal)
        simulated_returns: List[float] = []
        worst_loss = 0.0

        for _ in range(num_simulations):
            port_ret = 0.0
            for asset in assets:
                mu = means.get(asset, 0.0)
                vol = max(cov_matrix.get(asset, {}).get(asset, 0.0), 1e-10) ** 0.5
                # Generate correlated return (simplified: independent)
                sim_ret = random.gauss(mu, vol)
                port_ret += weights.get(asset, 0.0) * sim_ret

            simulated_returns.append(port_ret)
            if port_ret < worst_loss:
                worst_loss = port_ret

        # Sort and find VaR
        sorted_returns = sorted(simulated_returns)
        var_idx = int((1.0 - confidence) * len(sorted_returns))
        var_ret = sorted_returns[var_idx]

        var_ret_scaled = var_ret * math.sqrt(horizon)
        var_value = abs(var_ret_scaled) * portfolio_value
        var_pct = abs(var_ret_scaled)

        # Expected shortfall
        tail = [r for r in sorted_returns if r <= var_ret]
        es = sum(tail) / len(tail) if tail else var_ret
        es_scaled = es * math.sqrt(horizon)

        return VaRReport(
            var_value=var_value,
            var_pct=var_pct,
            confidence=confidence,
            method=VaRMethod.MONTE_CARLO,
            horizon_days=horizon,
            portfolio_value=portfolio_value,
            worst_loss=abs(worst_loss) * portfolio_value,
            expected_shortfall=abs(es_scaled) * portfolio_value,
            metadata={"num_simulations": num_simulations},
        )

    # ── helpers ────────────────────────────────────────────────────────────

    def _normal_quantile(self, p: float) -> float:
        """Approximate normal quantile using Beasley-Springer-Moro."""
        # Simplified lookup for common confidence levels
        quantiles = {
            0.90: 1.2816,
            0.95: 1.6449,
            0.975: 1.9600,
            0.99: 2.3263,
            0.995: 2.5758,
            0.999: 3.0902,
        }
        return quantiles.get(round(p, 3), 1.6449)

    def _normal_pdf(self, x: float) -> float:
        """Standard normal PDF."""
        return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)

    def _synthetic_returns(
        self, assets: List[str], periods: int
    ) -> Dict[str, List[float]]:
        random.seed(42)
        returns: Dict[str, List[float]] = {}
        for asset in assets:
            mu = random.uniform(-0.001, 0.002)
            sigma = random.uniform(0.01, 0.05)
            returns[asset] = [
                random.gauss(mu, sigma) for _ in range(periods)
            ]
        return returns

    def _synthetic_cov(
        self, assets: List[str]
    ) -> Dict[str, Dict[str, float]]:
        random.seed(42)
        cov: Dict[str, Dict[str, float]] = {
            a: {b: 0.0 for b in assets} for a in assets
        }
        for i in assets:
            for j in assets:
                if i == j:
                    cov[i][j] = random.uniform(0.02, 0.08)
                else:
                    cov[i][j] = random.uniform(-0.01, 0.02)
        return cov
