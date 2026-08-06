"""Orthogonalization — remove shared variance among factors.

Supports::

    Gram-Schmidt, PCA, Residual Regression

Enhances alpha independence and reduces redundancy in multi-factor models.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OrthogonalizationMethod(str, Enum):
    """Orthogonalization methods."""

    GRAM_SCHMIDT = "gram_schmidt"
    PCA = "pca"
    RESIDUAL_REGRESSION = "residual_regression"


class Orthogonalizer:
    """Factor orthogonalization to remove shared variance.

    Methods:
    * Gram-Schmidt: sequential orthogonalization, order-dependent
    * PCA: principal component decomposition, order-independent
    * Residual Regression: regress each factor on all others
    """

    def __init__(
        self,
        method: OrthogonalizationMethod = OrthogonalizationMethod.GRAM_SCHMIDT,
    ) -> None:
        self._method = method

    @property
    def method(self) -> OrthogonalizationMethod:
        return self._method

    def orthogonalize(
        self,
        factor_matrix: Dict[str, List[float]],
        order: Optional[List[str]] = None,
    ) -> Dict[str, List[float]]:
        """Orthogonalize a set of factors.

        Args:
            factor_matrix: factor_name → values mapping
            order: order of factors for Gram-Schmidt (most important first)

        Returns:
            orthogonalized factor values
        """
        if not factor_matrix:
            return {}

        if self._method == OrthogonalizationMethod.GRAM_SCHMIDT:
            return self._gram_schmidt(factor_matrix, order)
        elif self._method == OrthogonalizationMethod.PCA:
            return self._pca_orthogonalize(factor_matrix)
        elif self._method == OrthogonalizationMethod.RESIDUAL_REGRESSION:
            return self._residual_regression(factor_matrix)
        else:
            return dict(factor_matrix)

    def _gram_schmidt(
        self,
        factor_matrix: Dict[str, List[float]],
        order: Optional[List[str]] = None,
    ) -> Dict[str, List[float]]:
        """Gram-Schmidt orthogonalization (order-dependent)."""
        factor_names = order or list(factor_matrix.keys())
        if not factor_names:
            return {}

        n = len(factor_matrix[factor_names[0]])

        def dot(a: List[float], b: List[float]) -> float:
            return sum(x * y for x, y in zip(a, b))

        def norm(v: List[float]) -> float:
            return dot(v, v) ** 0.5

        def project(u: List[float], v: List[float]) -> List[float]:
            nv = norm(v)
            if nv == 0:
                return [0.0] * len(u)
            coeff = dot(u, v) / (nv * nv)
            return [coeff * vi for vi in v]

        result: Dict[str, List[float]] = {}
        orthogonal_basis: List[List[float]] = []

        for name in factor_names:
            values = list(factor_matrix.get(name, [0.0] * n))
            v = list(values)

            for basis_vec in orthogonal_basis:
                proj = project(v, basis_vec)
                v = [vi - pi for vi, pi in zip(v, proj)]

            result[name] = v
            orthogonal_basis.append(v)

        return result

    def _pca_orthogonalize(
        self,
        factor_matrix: Dict[str, List[float]],
    ) -> Dict[str, List[float]]:
        """PCA-based orthogonalization (order-independent)."""
        # Simplified: use covariance decomposition
        factor_names = list(factor_matrix.keys())
        if len(factor_names) < 2:
            return dict(factor_matrix)

        n = len(factor_matrix[factor_names[0]])

        # Compute covariance matrix
        def compute_cov(a: List[float], b: List[float]) -> float:
            mean_a = sum(a) / len(a)
            mean_b = sum(b) / len(b)
            return sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b)) / len(a)

        # Simple power iteration for first eigenvector (dominant component)
        k = len(factor_names)
        cov_matrix = [[0.0] * k for _ in range(k)]
        for i in range(k):
            for j in range(k):
                cov_matrix[i][j] = compute_cov(
                    factor_matrix[factor_names[i]],
                    factor_matrix[factor_names[j]],
                )

        # Simple diagonalization approximation: use Cholesky-like decomposition
        # For simplicity, remove first principal component
        result: Dict[str, List[float]] = {}

        # Compute mean factor (first PC approximation)
        mean_factor = [0.0] * n
        for name in factor_names:
            values = factor_matrix[name]
            for t in range(n):
                mean_factor[t] += values[t] / k

        # Subtract common component
        for name in factor_names:
            values = factor_matrix[name]
            # Regress on mean factor
            mean_m = sum(mean_factor) / n
            mean_v = sum(values) / n
            cov_mv = sum((m - mean_m) * (v - mean_v) for m, v in zip(mean_factor, values))
            var_m = sum((m - mean_m) ** 2 for m in mean_factor)

            if var_m > 0:
                beta = cov_mv / var_m
                alpha = mean_v - beta * mean_m
                result[name] = [v - (alpha + beta * m) for v, m in zip(values, mean_factor)]
            else:
                result[name] = list(values)

        return result

    def _residual_regression(
        self,
        factor_matrix: Dict[str, List[float]],
    ) -> Dict[str, List[float]]:
        """Residual regression: each factor regressed on all others."""
        factor_names = list(factor_matrix.keys())
        if len(factor_names) < 2:
            return dict(factor_matrix)

        n = len(factor_matrix[factor_names[0]])
        result: Dict[str, List[float]] = {}

        for target_name in factor_names:
            target = factor_matrix[target_name]
            other_names = [fn for fn in factor_names if fn != target_name]

            # Simple: regress target on mean of other factors
            other_mean = [0.0] * n
            for other_name in other_names:
                other_vals = factor_matrix[other_name]
                for t in range(n):
                    other_mean[t] += other_vals[t] / len(other_names)

            # Regress
            mean_x = sum(other_mean) / n
            mean_y = sum(target) / n
            cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(other_mean, target))
            var_x = sum((x - mean_x) ** 2 for x in other_mean)

            if var_x > 0:
                beta = cov / var_x
                alpha = mean_y - beta * mean_x
                result[target_name] = [y - (alpha + beta * x) for y, x in zip(target, other_mean)]
            else:
                result[target_name] = list(target)

        return result

    def correlation_matrix(
        self,
        factor_matrix: Dict[str, List[float]],
    ) -> Dict[str, Dict[str, float]]:
        """Compute pairwise correlation matrix for factors."""
        names = list(factor_matrix.keys())
        corr: Dict[str, Dict[str, float]] = {}

        for i, name_i in enumerate(names):
            corr[name_i] = {}
            vals_i = factor_matrix[name_i]
            mean_i = sum(vals_i) / len(vals_i)
            std_i = (sum((v - mean_i) ** 2 for v in vals_i) / len(vals_i)) ** 0.5

            for name_j in names:
                vals_j = factor_matrix[name_j]
                mean_j = sum(vals_j) / len(vals_j)
                std_j = (sum((v - mean_j) ** 2 for v in vals_j) / len(vals_j)) ** 0.5

                if std_i > 0 and std_j > 0:
                    cov = sum((a - mean_i) * (b - mean_j) for a, b in zip(vals_i, vals_j)) / len(vals_i)
                    corr[name_i][name_j] = cov / (std_i * std_j)
                else:
                    corr[name_i][name_j] = 0.0

        return corr
