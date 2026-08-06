"""CVaR Model — Conditional Value at Risk (Expected Shortfall) estimation.

CVaR (also called Expected Shortfall) measures the expected loss
beyond the VaR threshold, providing a more complete tail risk picture.

Supports methods:
* Historical — empirical expected shortfall
* Parametric — normal distribution ES
* Monte Carlo — simulated expected shortfall
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CVaRReport:
    """Conditional Value at Risk analysis report."""

    cvar_value: float = 0.0
    cvar_pct: float = 0.0
    var_value: float = 0.0
    var_pct: float = 0.0
    confidence: float = 0.95
    method: str = "historical"
    horizon_days: int = 1
    portfolio_value: float = 1.0
    tail_observations: int = 0
    max_tail_loss: float = 0.0
    tail_losses: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cvar_value": self.cvar_value,
            "cvar_pct": self.cvar_pct,
            "var_value": self.var_value,
            "var_pct": self.var_pct,
            "confidence": self.confidence,
            "method": self.method,
            "horizon_days": self.horizon_days,
            "portfolio_value": self.portfolio_value,
            "tail_observations": self.tail_observations,
            "max_tail_loss": self.max_tail_loss,
            "cvar_var_ratio": (
                self.cvar_value / self.var_value if self.var_value > 0 else 0.0
            ),
            "metadata": self.metadata,
        }


class CVaRModel:
    """Conditional Value at Risk (Expected Shortfall) estimation.

    CVaR at confidence level α is the expected loss given that
    the loss exceeds the VaR at level α.

    Advantages over VaR:
    * Coherent risk measure (sub-additive)
    * Captures tail shape beyond VaR threshold
    * Better for optimization
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
    ) -> CVaRReport:
        """Compute Conditional Value at Risk.

        Args:
            weights: Portfolio weights.
            confidence: Confidence level.
            method: 'historical', 'parametric', or 'monte_carlo'.
            horizon_days: Risk horizon in days.
            portfolio_value: Total portfolio value.
            returns_data: Historical returns per asset.
            cov_matrix: Covariance matrix.

        Returns:
            CVaRReport with CVaR and VaR estimates.
        """

        if method == "historical":
            return self._historical_cvar(
                weights, confidence, horizon_days,
                portfolio_value, returns_data,
            )
        elif method == "parametric":
            return self._parametric_cvar(
                weights, confidence, horizon_days,
                portfolio_value, cov_matrix,
            )
        elif method == "monte_carlo":
            return self._monte_carlo_cvar(
                weights, confidence, horizon_days,
                portfolio_value, returns_data, cov_matrix,
                kwargs.get("num_simulations", self._default_simulations),
            )
        else:
            return self._historical_cvar(
                weights, confidence, horizon_days,
                portfolio_value, returns_data,
            )

    def _historical_cvar(
        self,
        weights: Dict[str, float],
        confidence: float,
        horizon: int,
        portfolio_value: float,
        returns_data: Optional[Dict[str, List[float]]],
    ) -> CVaRReport:
        """Historical simulation CVaR."""
        if returns_data is None:
            returns_data = self._synthetic_returns(list(weights.keys()), 252)

        assets = list(weights.keys())
        T = min(len(returns_data.get(a, [])) for a in assets)

        # Portfolio returns
        portfolio_returns: List[float] = []
        for t in range(T):
            ret = sum(
                weights.get(a, 0.0) * returns_data.get(a, [])[t]
                for a in assets
            )
            portfolio_returns.append(ret)

        sorted_returns = sorted(portfolio_returns)

        # VaR
        var_idx = int((1.0 - confidence) * len(sorted_returns))
        var_ret = sorted_returns[var_idx]

        # CVaR: average of returns beyond VaR
        tail = [r for r in sorted_returns if r <= var_ret]
        cvar_ret = sum(tail) / len(tail) if tail else var_ret

        # Scale to horizon
        var_ret_scaled = var_ret * math.sqrt(horizon)
        cvar_ret_scaled = cvar_ret * math.sqrt(horizon)

        return CVaRReport(
            cvar_value=abs(cvar_ret_scaled) * portfolio_value,
            cvar_pct=abs(cvar_ret_scaled),
            var_value=abs(var_ret_scaled) * portfolio_value,
            var_pct=abs(var_ret_scaled),
            confidence=confidence,
            method="historical",
            horizon_days=horizon,
            portfolio_value=portfolio_value,
            tail_observations=len(tail),
            max_tail_loss=abs(min(tail)) * portfolio_value if tail else 0.0,
            tail_losses=tail,
            metadata={"num_observations": T},
        )

    def _parametric_cvar(
        self,
        weights: Dict[str, float],
        confidence: float,
        horizon: int,
        portfolio_value: float,
        cov_matrix: Optional[Dict[str, Dict[str, float]]],
    ) -> CVaRReport:
        """Parametric CVaR assuming normal distribution."""
        if cov_matrix is None:
            cov_matrix = self._synthetic_cov(list(weights.keys()))

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

        # Z-score
        z_score = self._normal_quantile(confidence)

        # VaR
        var_ret = z_score * portfolio_vol * math.sqrt(horizon)

        # CVaR for normal: σ * φ(z) / (1-α) * sqrt(T)
        phi_z = math.exp(-0.5 * z_score * z_score) / math.sqrt(2 * math.pi)
        cvar_ret = portfolio_vol * phi_z / (1.0 - confidence) * math.sqrt(horizon)

        return CVaRReport(
            cvar_value=abs(cvar_ret) * portfolio_value,
            cvar_pct=abs(cvar_ret) / math.sqrt(horizon),
            var_value=abs(var_ret) * portfolio_value,
            var_pct=abs(var_ret) / math.sqrt(horizon),
            confidence=confidence,
            method="parametric",
            horizon_days=horizon,
            portfolio_value=portfolio_value,
            tail_observations=0,
            max_tail_loss=abs(cvar_ret) * 2.0 * portfolio_value,
            metadata={"portfolio_volatility": portfolio_vol, "z_score": z_score},
        )

    def _monte_carlo_cvar(
        self,
        weights: Dict[str, float],
        confidence: float,
        horizon: int,
        portfolio_value: float,
        returns_data: Optional[Dict[str, List[float]]],
        cov_matrix: Optional[Dict[str, Dict[str, float]]],
        num_simulations: int,
    ) -> CVaRReport:
        """Monte Carlo simulation CVaR."""
        if cov_matrix is None:
            cov_matrix = self._synthetic_cov(list(weights.keys()))

        assets = list(weights.keys())

        if returns_data:
            means = {
                a: sum(returns_data[a]) / len(returns_data[a])
                for a in assets
            }
        else:
            means = {a: 0.0 for a in assets}

        simulated_returns: List[float] = []
        for _ in range(num_simulations):
            port_ret = 0.0
            for asset in assets:
                mu = means.get(asset, 0.0)
                vol = max(
                    cov_matrix.get(asset, {}).get(asset, 0.0), 1e-10
                ) ** 0.5
                port_ret += weights.get(asset, 0.0) * random.gauss(mu, vol)
            simulated_returns.append(port_ret)

        sorted_returns = sorted(simulated_returns)
        var_idx = int((1.0 - confidence) * len(sorted_returns))
        var_ret = sorted_returns[var_idx]

        tail = [r for r in sorted_returns if r <= var_ret]
        cvar_ret = sum(tail) / len(tail) if tail else var_ret

        var_ret_scaled = var_ret * math.sqrt(horizon)
        cvar_ret_scaled = cvar_ret * math.sqrt(horizon)

        return CVaRReport(
            cvar_value=abs(cvar_ret_scaled) * portfolio_value,
            cvar_pct=abs(cvar_ret_scaled),
            var_value=abs(var_ret_scaled) * portfolio_value,
            var_pct=abs(var_ret_scaled),
            confidence=confidence,
            method="monte_carlo",
            horizon_days=horizon,
            portfolio_value=portfolio_value,
            tail_observations=len(tail),
            max_tail_loss=abs(min(tail)) * portfolio_value if tail else 0.0,
            tail_losses=tail,
            metadata={"num_simulations": num_simulations},
        )

    def _normal_quantile(self, p: float) -> float:
        quantiles = {
            0.90: 1.2816, 0.95: 1.6449, 0.975: 1.9600,
            0.99: 2.3263, 0.995: 2.5758, 0.999: 3.0902,
        }
        return quantiles.get(round(p, 3), 1.6449)

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
