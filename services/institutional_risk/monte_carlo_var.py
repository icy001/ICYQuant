"""MonteCarloVar — Monte Carlo simulation VaR.

Simulates return paths using fitted distributions and correlation
structure to produce robust VaR estimates.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class MonteCarloVaRResult:
    """Monte Carlo VaR result."""

    var_95: float = 0.0
    var_99: float = 0.0
    var_995: float = 0.0
    expected_shortfall_95: float = 0.0
    expected_shortfall_99: float = 0.0
    mean_simulated: float = 0.0
    std_simulated: float = 0.0
    min_simulated: float = 0.0
    max_simulated: float = 0.0
    simulations: int = 0
    seed: Optional[int] = None
    convergence_achieved: bool = True


class MonteCarloVaREngine:
    """Monte Carlo VaR engine with correlation-aware simulations.

    Usage::

        engine = MonteCarloVaREngine(simulations=50000, seed=42)
        result = engine.compute_single(returns)
        print(f"MC VaR 99%: {result.var_99:.0f}")
    """

    def __init__(self, simulations: int = 10000, seed: Optional[int] = None):
        self._simulations = simulations
        self._rng = random.Random(seed) if seed else random.Random()

    def compute_single(
        self,
        returns: List[float],
        confidence_levels: Optional[List[float]] = None,
    ) -> MonteCarloVaRResult:
        """Compute MC VaR for a single return series.

        Simulates returns from fitted normal distribution.
        """
        if len(returns) < 2:
            return MonteCarloVaRResult(simulations=self._simulations)

        # fit distribution
        n = len(returns)
        mu = sum(returns) / n
        variance = sum((r - mu) ** 2 for r in returns) / (n - 1)
        sigma = math.sqrt(max(variance, 0.0))

        # simulate
        simulated = []
        for _ in range(self._simulations):
            z = self._normal_random()
            simulated.append(mu + z * sigma)

        simulated.sort()

        cl = confidence_levels or [0.95, 0.99, 0.995]

        result = MonteCarloVaRResult(simulations=self._simulations, seed=None)

        if 0.95 in cl:
            result.var_95 = abs(simulated[int(self._simulations * 0.05)])
        if 0.99 in cl:
            result.var_99 = abs(simulated[int(self._simulations * 0.01)])
        if 0.995 in cl:
            result.var_995 = abs(simulated[int(self._simulations * 0.005)])

        # expected shortfall
        result.expected_shortfall_95 = self._compute_es(simulated, 0.95)
        result.expected_shortfall_99 = self._compute_es(simulated, 0.99)

        # stats
        result.mean_simulated = sum(simulated) / len(simulated)
        result.std_simulated = sigma
        result.min_simulated = simulated[0]
        result.max_simulated = simulated[-1]

        return result

    def compute_portfolio(
        self,
        returns_dict: Dict[str, List[float]],
        weights: Dict[str, float],
        confidence_levels: Optional[List[float]] = None,
    ) -> MonteCarloVaRResult:
        """Compute MC VaR for a portfolio with correlation structure.

        Uses Cholesky decomposition of the covariance matrix.
        """
        keys = sorted(set(returns_dict.keys()) & set(weights.keys()))
        n_assets = len(keys)

        if n_assets == 0:
            return MonteCarloVaRResult()

        # fit marginals
        mus = []
        sigmas = []
        min_len = min(len(returns_dict[k]) for k in keys)

        for k in keys:
            data = returns_dict[k][:min_len]
            mu = sum(data) / len(data)
            var = sum((r - mu) ** 2 for r in data) / (len(data) - 1)
            mus.append(mu)
            sigmas.append(math.sqrt(max(var, 0.0)))

        # correlation matrix
        corr = self._correlation_matrix(
            {k: returns_dict[k][:min_len] for k in keys}
        )

        # Cholesky decomposition (simple 2D)
        L = self._cholesky(corr)

        # simulate
        portfolio_returns = []
        for _ in range(self._simulations):
            # independent normals
            z = [self._normal_random() for _ in range(n_assets)]
            # correlate
            e = [sum(L[i][j] * z[j] for j in range(n_assets)) for i in range(n_assets)]
            # asset returns
            asset_rets = [mus[i] + sigmas[i] * e[i] for i in range(n_assets)]
            # portfolio return
            port_ret = sum(weights.get(keys[i], 0.0) * asset_rets[i] for i in range(n_assets))
            portfolio_returns.append(port_ret)

        portfolio_returns.sort()

        result = MonteCarloVaRResult(simulations=self._simulations, seed=None)
        result.var_95 = abs(portfolio_returns[int(self._simulations * 0.05)])
        result.var_99 = abs(portfolio_returns[int(self._simulations * 0.01)])
        result.expected_shortfall_95 = self._compute_es(portfolio_returns, 0.95)
        result.expected_shortfall_99 = self._compute_es(portfolio_returns, 0.99)
        result.mean_simulated = sum(portfolio_returns) / len(portfolio_returns)

        return result

    # ── helpers ─────────────────────────────────────────────────────

    def _normal_random(self) -> float:
        """Box-Muller transform for standard normal."""
        u1 = self._rng.random()
        u2 = self._rng.random()
        return math.sqrt(-2 * math.log(max(u1, 1e-10))) * math.cos(2 * math.pi * u2)

    def _compute_es(self, sorted_returns: List[float], confidence: float) -> float:
        """Expected shortfall = average of worst (1-confidence)% losses."""
        n = len(sorted_returns)
        tail_count = int(n * (1 - confidence))
        if tail_count == 0:
            return 0.0
        tail_losses = sorted_returns[:tail_count]
        return abs(sum(tail_losses) / len(tail_losses))

    def _correlation_matrix(
        self, returns_dict: Dict[str, List[float]]
    ) -> List[List[float]]:
        """Compute correlation matrix."""
        keys = sorted(returns_dict.keys())
        n = len(keys)
        series = [returns_dict[k] for k in keys]
        m = min(len(s) for s in series)
        corr = [[1.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(i + 1, n):
                s1, s2 = series[i][:m], series[j][:m]
                mu1 = sum(s1) / m
                mu2 = sum(s2) / m
                cov = sum((x - mu1) * (y - mu2) for x, y in zip(s1, s2)) / (m - 1)
                v1 = sum((x - mu1) ** 2 for x in s1) / (m - 1)
                v2 = sum((y - mu2) ** 2 for y in s2) / (m - 1)
                if v1 > 0 and v2 > 0:
                    c = cov / (math.sqrt(v1) * math.sqrt(v2))
                    c = max(-1.0, min(1.0, c))
                else:
                    c = 0.0
                corr[i][j] = c
                corr[j][i] = c

        return corr

    def _cholesky(self, A: List[List[float]]) -> List[List[float]]:
        """Cholesky decomposition (simple, for small matrices)."""
        n = len(A)
        L = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1):
                s = sum(L[i][k] * L[j][k] for k in range(j))
                if i == j:
                    L[i][j] = math.sqrt(max(A[i][i] - s, 1e-10))
                else:
                    L[i][j] = (A[i][j] - s) / max(L[j][j], 1e-10)
        return L
