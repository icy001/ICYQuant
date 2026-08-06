"""Hierarchical Risk Parity (HRP) Optimizer — machine learning-based allocation.

Implements the HRP algorithm (Lopez de Prado):
1. Hierarchical clustering on correlation matrix
2. Quasi-diagonalization (reorder assets)
3. Recursive bisection allocation

Advantages: robust for high-dimensional portfolios, no matrix inversion.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from .optimizer import Optimizer, OptimizerType, OptimizeResult, OptimizeStatus

logger = logging.getLogger(__name__)


class HRPOptimizer(Optimizer):
    """Hierarchical Risk Parity optimizer.

    Uses hierarchical clustering and recursive bisection to
    allocate weights without inverting the covariance matrix,
    making it robust for high-dimensional portfolios.
    """

    def __init__(
        self,
        cov_matrix: Optional[Dict[str, Dict[str, float]]] = None,
        expected_returns: Optional[Dict[str, float]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        linkage_method: str = "single",
        **kwargs: Any,
    ) -> None:
        super().__init__(cov_matrix, expected_returns, constraints, **kwargs)
        self._linkage_method = linkage_method

    async def optimize(self) -> OptimizeResult:
        """Run HRP optimization."""
        assets = self.assets
        if not assets:
            return OptimizeResult(
                weights={},
                optimizer_type=OptimizerType.HRP,
                status=OptimizeStatus.INFEASIBLE,
                messages=["No assets in universe"],
            )

        n = len(assets)

        # Step 1: Compute correlation matrix from covariance
        corr_matrix = self._cov_to_corr(assets)

        # Step 2: Compute distance matrix
        dist_matrix = self._corr_to_dist(corr_matrix, assets)

        # Step 3: Hierarchical clustering → ordered assets
        ordered = self._hierarchical_cluster(dist_matrix, assets)

        # Step 4: Recursive bisection allocation
        weights = self._recursive_bisection(ordered)

        # Apply constraints
        weights = self._apply_constraints(weights)

        ret = self._compute_portfolio_return(weights)
        risk = self._compute_portfolio_risk(weights)
        sharpe = self._compute_sharpe(ret, risk)
        constraints_ok = self._check_constraints(weights)

        return OptimizeResult(
            weights=weights,
            optimizer_type=OptimizerType.HRP,
            status=OptimizeStatus.OPTIMAL if constraints_ok else OptimizeStatus.FEASIBLE,
            expected_return=ret,
            expected_risk=risk,
            sharpe_ratio=sharpe,
            constraints_satisfied=constraints_ok,
            metadata={
                "linkage_method": self._linkage_method,
                "cluster_order": ordered,
            },
        )

    def _cov_to_corr(
        self, assets: List[str]
    ) -> Dict[str, Dict[str, float]]:
        """Convert covariance matrix to correlation matrix."""
        corr: Dict[str, Dict[str, float]] = {}
        for i in assets:
            corr[i] = {}
            vol_i = max(self._cov_matrix.get(i, {}).get(i, 0.0), 1e-10) ** 0.5
            for j in assets:
                cov_ij = self._cov_matrix.get(i, {}).get(j, 0.0)
                vol_j = max(self._cov_matrix.get(j, {}).get(j, 0.0), 1e-10) ** 0.5
                corr[i][j] = cov_ij / (vol_i * vol_j) if vol_i * vol_j > 0 else 0.0
        return corr

    def _corr_to_dist(
        self,
        corr: Dict[str, Dict[str, float]],
        assets: List[str],
    ) -> Dict[str, Dict[str, float]]:
        """Convert correlation to distance: d = sqrt(0.5 * (1 - ρ))."""
        dist: Dict[str, Dict[str, float]] = {}
        for i in assets:
            dist[i] = {}
            for j in assets:
                rho = corr.get(i, {}).get(j, 0.0)
                d = math.sqrt(max(0.5 * (1.0 - rho), 0.0))
                dist[i][j] = d
        return dist

    def _hierarchical_cluster(
        self,
        dist: Dict[str, Dict[str, float]],
        assets: List[str],
    ) -> List[str]:
        """Perform single-linkage hierarchical clustering.

        Returns assets in quasi-diagonal order.
        """
        n = len(assets)
        if n <= 2:
            return list(assets)

        remaining = set(assets)
        clusters: List[List[str]] = [[a] for a in assets]

        while len(clusters) > 1:
            # Find closest pair of clusters
            min_dist = float("inf")
            min_i, min_j = 0, 0

            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    d = self._cluster_distance(dist, clusters[i], clusters[j])
                    if d < min_dist:
                        min_dist = d
                        min_i, min_j = i, j

            # Merge closest clusters
            new_cluster = clusters[min_i] + clusters[min_j]
            clusters.pop(max(min_i, min_j))
            clusters.pop(min(min_i, min_j))
            clusters.append(new_cluster)

        return clusters[0] if clusters else list(assets)

    def _cluster_distance(
        self,
        dist: Dict[str, Dict[str, float]],
        c1: List[str],
        c2: List[str],
    ) -> float:
        """Compute distance between two clusters."""
        if self._linkage_method == "single":
            # Single linkage: minimum distance
            min_d = float("inf")
            for a in c1:
                for b in c2:
                    d = dist.get(a, {}).get(b, float("inf"))
                    if d < min_d:
                        min_d = d
            return min_d
        else:
            # Average linkage
            total = 0.0
            count = 0
            for a in c1:
                for b in c2:
                    total += dist.get(a, {}).get(b, 0.0)
                    count += 1
            return total / count if count > 0 else float("inf")

    def _recursive_bisection(self, ordered: List[str]) -> Dict[str, float]:
        """Recursive bisection allocation on ordered assets.

        At each split, allocate weight inversely proportional to
        the cluster variance.
        """
        n = len(ordered)
        weights = {a: 1.0 for a in ordered}

        self._bisect(ordered, weights)

        # Normalize
        total = sum(weights.values())
        if total > 0:
            weights = {a: w / total for a, w in weights.items()}

        return weights

    def _bisect(
        self, cluster: List[str], weights: Dict[str, float]
    ) -> None:
        """Recursively bisect a cluster and assign weights."""
        if len(cluster) <= 1:
            return

        # Split cluster into two halves
        mid = len(cluster) // 2
        left = cluster[:mid]
        right = cluster[mid:]

        # Compute variance of each sub-cluster
        var_left = self._cluster_variance(left)
        var_right = self._cluster_variance(right)

        # Allocate weight inversely proportional to variance
        inv_left = 1.0 / max(var_left, 1e-10)
        inv_right = 1.0 / max(var_right, 1e-10)
        total_inv = inv_left + inv_right

        alpha_left = inv_left / total_inv if total_inv > 0 else 0.5
        alpha_right = 1.0 - alpha_left

        # Scale weights within each sub-cluster
        for asset in left:
            weights[asset] *= alpha_left
        for asset in right:
            weights[asset] *= alpha_right

        # Recurse
        self._bisect(left, weights)
        self._bisect(right, weights)

    def _cluster_variance(self, cluster: List[str]) -> float:
        """Compute portfolio variance for a cluster (equal weight within)."""
        if not cluster:
            return 0.0
        n = len(cluster)
        w = 1.0 / n
        variance = 0.0
        for i in cluster:
            for j in cluster:
                cov_ij = self._cov_matrix.get(i, {}).get(j, 0.0)
                variance += w * w * cov_ij
        return max(variance, 0.0)

    def _apply_constraints(
        self, weights: Dict[str, float]
    ) -> Dict[str, float]:
        long_only = self._constraints.get("long_only", True)
        min_w = self._constraints.get("min_weight", 0.0)
        max_w = self._constraints.get("max_weight", 1.0)

        for asset in weights:
            if long_only and weights[asset] < 0:
                weights[asset] = 0.0
            weights[asset] = max(min_w, min(weights[asset], max_w))

        total = sum(weights.values())
        if total > 0:
            weights = {a: w / total for a, w in weights.items()}

        return weights
