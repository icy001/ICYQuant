"""Covariance Estimator — robust covariance matrix estimation.

Supports estimation methods:
* Sample Covariance — standard historical covariance
* Shrinkage (Ledoit-Wolf) — shrinks toward structured target
* EWMA — exponentially weighted moving average
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CovarianceMethod(str, Enum):
    """Covariance estimation methods."""

    SAMPLE = "sample"
    SHRINKAGE = "shrinkage"
    EWMA = "ewma"


@dataclass
class CovarianceResult:
    """Covariance estimation result."""

    matrix: Dict[str, Dict[str, float]]
    method: CovarianceMethod
    num_assets: int
    num_observations: int
    condition_number: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method.value,
            "num_assets": self.num_assets,
            "num_observations": self.num_observations,
            "condition_number": self.condition_number,
            "metadata": self.metadata,
        }


class CovarianceEstimator:
    """Robust covariance matrix estimation.

    Provides multiple methods for estimating the covariance matrix
    used by optimizers and risk models.
    """

    def __init__(self) -> None:
        pass

    async def estimate(
        self,
        universe: List[str],
        returns_data: Optional[Dict[str, List[float]]] = None,
        method: str = "shrinkage",
        decay: float = 0.94,
        **kwargs: Any,
    ) -> CovarianceResult:
        """Estimate covariance matrix.

        Args:
            universe: List of asset identifiers.
            returns_data: Dict of asset → list of historical returns.
            method: Estimation method.
            decay: Decay factor for EWMA.

        Returns:
            CovarianceResult with matrix and diagnostics.
        """
        if not universe:
            return CovarianceResult(
                matrix={},
                method=CovarianceMethod(method),
                num_assets=0,
                num_observations=0,
            )

        # Generate synthetic returns if none provided
        if returns_data is None:
            returns_data = self._synthetic_returns(universe, 252)

        est_method = CovarianceMethod(method)

        if est_method == CovarianceMethod.SAMPLE:
            matrix = self._sample_cov(universe, returns_data)
        elif est_method == CovarianceMethod.SHRINKAGE:
            matrix = self._shrinkage_cov(universe, returns_data)
        elif est_method == CovarianceMethod.EWMA:
            matrix = self._ewma_cov(universe, returns_data, decay)
        else:
            matrix = self._sample_cov(universe, returns_data)

        # Compute condition number
        cond = self._estimate_condition_number(matrix, universe)

        return CovarianceResult(
            matrix=matrix,
            method=est_method,
            num_assets=len(universe),
            num_observations=len(next(iter(returns_data.values()), [])),
            condition_number=cond,
        )

    def _sample_cov(
        self,
        universe: List[str],
        returns_data: Dict[str, List[float]],
    ) -> Dict[str, Dict[str, float]]:
        """Standard sample covariance matrix."""
        n = len(universe)
        T = min(len(returns_data.get(a, [])) for a in universe)
        if T < 2:
            # Return identity-like matrix
            return {a: {b: 0.04 if a == b else 0.0 for b in universe} for a in universe}

        # Compute mean returns
        means = {
            a: sum(returns_data.get(a, [])) / T for a in universe
        }

        # Compute covariance
        cov: Dict[str, Dict[str, float]] = {
            a: {b: 0.0 for b in universe} for a in universe
        }

        for t in range(T):
            for i in universe:
                dev_i = returns_data.get(i, [])[t] - means[i]
                for j in universe:
                    dev_j = returns_data.get(j, [])[t] - means[j]
                    cov[i][j] += dev_i * dev_j

        # Normalize
        for i in universe:
            for j in universe:
                cov[i][j] /= (T - 1)

        return cov

    def _shrinkage_cov(
        self,
        universe: List[str],
        returns_data: Dict[str, List[float]],
    ) -> Dict[str, Dict[str, float]]:
        """Ledoit-Wolf shrinkage covariance.

        Shrinks sample covariance toward a structured target
        (constant correlation) to improve estimation.
        """
        sample_cov = self._sample_cov(universe, returns_data)
        n = len(universe)

        # Target: constant correlation matrix
        # Compute average correlation
        avg_corr = 0.0
        count = 0
        for i in universe:
            for j in universe:
                if i != j:
                    vol_i = max(sample_cov[i][i], 1e-10) ** 0.5
                    vol_j = max(sample_cov[j][j], 1e-10) ** 0.5
                    corr = sample_cov[i][j] / (vol_i * vol_j) if vol_i * vol_j > 0 else 0.0
                    avg_corr += corr
                    count += 1
        avg_corr = avg_corr / count if count > 0 else 0.0

        # Build target matrix
        target: Dict[str, Dict[str, float]] = {
            a: {b: 0.0 for b in universe} for a in universe
        }
        for i in universe:
            for j in universe:
                if i == j:
                    target[i][j] = sample_cov[i][i]
                else:
                    vol_i = max(sample_cov[i][i], 1e-10) ** 0.5
                    vol_j = max(sample_cov[j][j], 1e-10) ** 0.5
                    target[i][j] = avg_corr * vol_i * vol_j

        # Shrinkage intensity (simplified: constant 0.3)
        delta = 0.3

        # Blend
        shrunk: Dict[str, Dict[str, float]] = {
            a: {b: 0.0 for b in universe} for a in universe
        }
        for i in universe:
            for j in universe:
                shrunk[i][j] = (1 - delta) * sample_cov[i][j] + delta * target[i][j]

        return shrunk

    def _ewma_cov(
        self,
        universe: List[str],
        returns_data: Dict[str, List[float]],
        decay: float = 0.94,
    ) -> Dict[str, Dict[str, float]]:
        """Exponentially weighted moving average covariance."""
        n = len(universe)
        T = min(len(returns_data.get(a, [])) for a in universe)

        cov: Dict[str, Dict[str, float]] = {
            a: {b: 0.0 for b in universe} for a in universe
        }

        # Compute means
        means = {a: sum(returns_data.get(a, [])) / T for a in universe}

        # EWMA
        weight_sum = 0.0
        for t in range(T):
            w = decay ** (T - 1 - t)
            weight_sum += w
            for i in universe:
                dev_i = returns_data.get(i, [])[t] - means[i]
                for j in universe:
                    dev_j = returns_data.get(j, [])[t] - means[j]
                    cov[i][j] += w * dev_i * dev_j

        if weight_sum > 0:
            for i in universe:
                for j in universe:
                    cov[i][j] /= weight_sum

        return cov

    def _estimate_condition_number(
        self,
        cov: Dict[str, Dict[str, float]],
        universe: List[str],
    ) -> float:
        """Estimate condition number via eigenvalue ratio."""
        if not universe:
            return 0.0
        # Simplified: use diagonal ratio as proxy
        diag = [max(cov.get(a, {}).get(a, 1e-10), 1e-10) for a in universe]
        return max(diag) / min(diag) if diag else 0.0

    def _synthetic_returns(
        self, universe: List[str], periods: int
    ) -> Dict[str, List[float]]:
        """Generate synthetic return data for testing."""
        import random
        random.seed(42)

        returns: Dict[str, List[float]] = {}
        for asset in universe:
            # Each asset has different mean and vol
            mu = random.uniform(-0.001, 0.002)
            sigma = random.uniform(0.01, 0.05)
            returns[asset] = [
                random.gauss(mu, sigma) for _ in range(periods)
            ]
        return returns
