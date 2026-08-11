"""VaREngine — unified Value-at-Risk computation engine.

Supports Historical, Parametric, and Monte Carlo VaR at multiple
confidence levels, with strategy/portfolio/capital-pool granularity.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple


class VaRMethod(Enum):
    HISTORICAL = auto()
    PARAMETRIC = auto()
    MONTE_CARLO = auto()


@dataclass
class VaRResult:
    """VaR computation result."""

    method: VaRMethod
    confidence_level: float
    var_value: float
    var_ratio: float = 0.0  # VaR / capital
    horizon_days: int = 1
    sample_size: int = 0
    data_points: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VaRConfig:
    """Configuration for VaR computations."""

    default_method: VaRMethod = VaRMethod.PARAMETRIC
    confidence_levels: List[float] = field(default_factory=lambda: [0.95, 0.99])
    default_horizon_days: int = 1
    historical_window: int = 252
    monte_carlo_simulations: int = 10000
    monte_carlo_seed: Optional[int] = None
    scipy_available: bool = False  # set True if scipy is installed


class VaREngine:
    """Unified VaR computation engine.

    Supports three methods:
    1. Historical: empirical percentile of historical returns
    2. Parametric: assuming normal distribution (mu - z*sigma)
    3. Monte Carlo: random simulations with correlation structure

    Usage::

        engine = VaREngine()
        var_99 = engine.compute(returns, confidence=0.99, method=VaRMethod.PARAMETRIC)
        var_95 = engine.compute(returns, confidence=0.95, method=VaRMethod.HISTORICAL)
    """

    # Z-scores for common confidence levels
    Z_SCORES = {
        0.90: 1.2816,
        0.95: 1.6449,
        0.975: 1.9600,
        0.99: 2.3263,
        0.995: 2.5758,
        0.999: 3.0902,
    }

    def __init__(self, config: Optional[VaRConfig] = None):
        self.config = config or VaRConfig()
        self._random = random.Random(self.config.monte_carlo_seed)

    # ── main compute ────────────────────────────────────────────────

    def compute(
        self,
        returns: List[float],
        confidence: float = 0.99,
        method: Optional[VaRMethod] = None,
        capital: float = 0.0,
        horizon_days: int = 1,
    ) -> VaRResult:
        """Compute VaR using the specified method.

        Args:
            returns: list of historical returns (in value terms, not percentages)
            confidence: confidence level (e.g., 0.99 for 99% VaR)
            method: VaR computation method
            capital: total capital for ratio computation
            horizon_days: time horizon in days
        """
        method = method or self.config.default_method

        if not returns:
            return VaRResult(method=method, confidence_level=confidence, var_value=0.0)

        if method == VaRMethod.HISTORICAL:
            var_val = self._historical_var(returns, confidence)
        elif method == VaRMethod.PARAMETRIC:
            var_val = self._parametric_var(returns, confidence)
        elif method == VaRMethod.MONTE_CARLO:
            var_val = self._monte_carlo_var(returns, confidence)
        else:
            var_val = 0.0

        # scale for horizon
        if horizon_days > 1:
            var_val *= math.sqrt(horizon_days)

        var_ratio = var_val / capital if capital > 0 else 0.0

        return VaRResult(
            method=method,
            confidence_level=confidence,
            var_value=var_val,
            var_ratio=var_ratio,
            horizon_days=horizon_days,
            sample_size=len(returns),
        )

    def compute_all(
        self,
        returns: List[float],
        capital: float = 0.0,
        method: Optional[VaRMethod] = None,
    ) -> Dict[float, VaRResult]:
        """Compute VaR at all configured confidence levels."""
        results = {}
        for cl in self.config.confidence_levels:
            results[cl] = self.compute(returns, cl, method, capital)
        return results

    # ── individual methods ─────────────────────────────────────────

    def _historical_var(self, returns: List[float], confidence: float) -> float:
        """Historical VaR: empirical percentile of sorted returns."""
        sorted_returns = sorted(returns)
        n = len(sorted_returns)
        # Find the (1 - confidence) percentile
        idx = int(n * (1 - confidence))
        idx = max(0, min(idx, n - 1))
        return abs(sorted_returns[idx])

    def _parametric_var(self, returns: List[float], confidence: float) -> float:
        """Parametric VaR: assuming normal distribution.

        VaR = -(mu + z_alpha * sigma)  [positive number]
        """
        if len(returns) < 2:
            return 0.0

        mu = sum(returns) / len(returns)
        variance = sum((r - mu) ** 2 for r in returns) / (len(returns) - 1)
        sigma = math.sqrt(variance) if variance > 0 else 0.0

        z_score = self.Z_SCORES.get(confidence, 2.3263)
        var_val = -(mu - z_score * sigma)  # negative returns → positive VaR
        # If returns are already in loss format, just mu - z*sigma
        # Standard: VaR = -(mu - z*sigma) for return data
        # For loss data: VaR = mu + z*sigma
        return max(0.0, var_val)

    def _monte_carlo_var(self, returns: List[float], confidence: float) -> float:
        """Monte Carlo VaR with simulated returns from fitted distribution."""
        if len(returns) < 2:
            return 0.0

        mu = sum(returns) / len(returns)
        variance = sum((r - mu) ** 2 for r in returns) / (len(returns) - 1)
        sigma = math.sqrt(variance) if variance > 0 else 0.0

        simulations = self.config.monte_carlo_simulations
        simulated = []
        for _ in range(simulations):
            # Box-Muller or simple normal approximation
            u1 = self._random.random()
            u2 = self._random.random()
            z = math.sqrt(-2 * math.log(max(u1, 1e-10))) * math.cos(2 * math.pi * u2)
            simulated.append(mu + z * sigma)

        simulated.sort()
        idx = int(simulations * (1 - confidence))
        idx = max(0, min(idx, simulations - 1))
        return abs(simulated[idx])

    # ── portfolio VaR ───────────────────────────────────────────────

    def compute_portfolio_var(
        self,
        strategy_returns: Dict[str, List[float]],
        weights: Dict[str, float],
        confidence: float = 0.99,
        method: Optional[VaRMethod] = None,
        total_capital: float = 0.0,
    ) -> VaRResult:
        """Compute portfolio-level VaR accounting for correlations.

        Args:
            strategy_returns: {strategy_id: [returns]}
            weights: {strategy_id: weight} (should sum to 1)
            confidence: confidence level
            method: computation method
            total_capital: for ratio computation
        """
        method = method or self.config.default_method
        common_keys = set(strategy_returns.keys()) & set(weights.keys())
        if not common_keys:
            return VaRResult(method=method, confidence_level=confidence, var_value=0.0)

        keys = sorted(common_keys)
        n = len(keys)

        # compute individual VaRs
        individual_vars = []
        for k in keys:
            var_result = self.compute(strategy_returns[k], confidence, method)
            individual_vars.append(var_result.var_value)

        # compute correlation matrix
        corr_matrix = self._compute_correlation_matrix(
            {k: strategy_returns[k] for k in keys}
        )

        # portfolio variance = w^T * Σ * w
        # where Σ = corr * diag(var) where var is VaR^2
        portfolio_var = 0.0
        for i in range(n):
            for j in range(n):
                w_i = weights.get(keys[i], 0.0)
                w_j = weights.get(keys[j], 0.0)
                var_i = individual_vars[i]
                var_j = individual_vars[j]
                corr = corr_matrix[i][j]
                portfolio_var += w_i * w_j * var_i * var_j * corr

        portfolio_var = math.sqrt(max(0.0, portfolio_var))
        var_ratio = portfolio_var / total_capital if total_capital > 0 else 0.0

        return VaRResult(
            method=method,
            confidence_level=confidence,
            var_value=portfolio_var,
            var_ratio=var_ratio,
        )

    # ── helpers ─────────────────────────────────────────────────────

    def _compute_correlation_matrix(
        self,
        returns_dict: Dict[str, List[float]],
    ) -> List[List[float]]:
        """Compute pairwise correlation matrix from return series."""
        keys = sorted(returns_dict.keys())
        n = len(keys)

        if n == 0:
            return []

        series = [returns_dict[k] for k in keys]
        min_len = min(len(s) for s in series)

        corr = [[1.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(i + 1, n):
                s_i = series[i][:min_len]
                s_j = series[j][:min_len]

                mu_i = sum(s_i) / len(s_i)
                mu_j = sum(s_j) / len(s_j)

                cov = sum((x - mu_i) * (y - mu_j) for x, y in zip(s_i, s_j)) / (len(s_i) - 1)
                var_i = sum((x - mu_i) ** 2 for x in s_i) / (len(s_i) - 1)
                var_j = sum((y - mu_j) ** 2 for y in s_j) / (len(s_j) - 1)

                if var_i > 0 and var_j > 0:
                    c = cov / (math.sqrt(var_i) * math.sqrt(var_j))
                    c = max(-1.0, min(1.0, c))
                else:
                    c = 0.0

                corr[i][j] = c
                corr[j][i] = c

        return corr

    def get_z_score(self, confidence: float) -> float:
        """Get the z-score for a given confidence level."""
        if confidence in self.Z_SCORES:
            return self.Z_SCORES[confidence]
        # interpolate
        sorted_cl = sorted(self.Z_SCORES.items())
        for i in range(len(sorted_cl) - 1):
            if sorted_cl[i][0] <= confidence <= sorted_cl[i + 1][0]:
                ratio = (confidence - sorted_cl[i][0]) / (sorted_cl[i + 1][0] - sorted_cl[i][0])
                return sorted_cl[i][1] + ratio * (sorted_cl[i + 1][1] - sorted_cl[i][1])
        return 2.3263  # default 99%
