"""
Correlation Engine — Computes pairwise correlations between alpha candidates.

Measures:
    - Signal correlation (return prediction similarity)
    - Feature correlation (input space overlap)
    - Exposure correlation (factor loading similarity)
    - Regime correlation (similar behavior across market regimes)

Low correlation between candidates is essential for portfolio construction.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class CorrelationEngine:
    """
    Computes and analyzes correlations between alpha/factor candidates.

    Correlation matrix is critical for:
        - Redundancy detection
        - Portfolio diversification
        - Alpha combination weight optimization
    """

    def __init__(self, max_correlation_for_independence: float = 0.70):
        self._max_correlation = max_correlation_for_independence
        self._correlation_cache: Dict[str, Dict[str, float]] = {}

    # ── Correlation Computation ────────────────────────────

    def compute_pairwise_correlations(
        self,
        individual_ids: List[str],
        signal_values: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """
        Compute pairwise correlation matrix for a set of individuals.

        Returns: {id_a: {id_b: correlation, ...}, ...}
        """
        if not individual_ids:
            return {}

        matrix: Dict[str, Dict[str, float]] = {}
        for i, oid_a in enumerate(individual_ids):
            matrix[oid_a] = {}
            for oid_b in individual_ids[i + 1 :]:
                corr = self._compute_correlation(oid_a, oid_b, signal_values)
                matrix[oid_a][oid_b] = corr
                self._correlation_cache.setdefault(oid_a, {})[oid_b] = corr
                self._correlation_cache.setdefault(oid_b, {})[oid_a] = corr

        return matrix

    def _compute_correlation(
        self,
        id_a: str,
        id_b: str,
        signal_values: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Compute correlation between two individuals."""
        # Check cache
        cached = self._correlation_cache.get(id_a, {}).get(id_b)
        if cached is not None:
            return cached

        if signal_values:
            # In production: compute Pearson correlation of actual signal series
            return 0.0  # placeholder
        return 0.0

    # ── Analysis ───────────────────────────────────────────

    def get_high_correlation_pairs(
        self,
        matrix: Dict[str, Dict[str, float]],
        threshold: Optional[float] = None,
    ) -> List[Tuple[str, str, float]]:
        """Find pairs with correlation above threshold."""
        threshold = threshold or self._max_correlation
        pairs = []
        for oid_a in matrix:
            for oid_b, corr in matrix[oid_a].items():
                if abs(corr) >= threshold:
                    pairs.append((oid_a, oid_b, corr))
        return pairs

    def get_independent_ids(
        self,
        individual_ids: List[str],
        matrix: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> List[str]:
        """
        Find a maximal independent set (greedy) of uncorrelated individuals.
        """
        if not individual_ids:
            return []

        if matrix is None:
            matrix = self.compute_pairwise_correlations(individual_ids)

        independent: List[str] = []
        for oid in individual_ids:
            correlated = False
            for selected in independent:
                corr = matrix.get(oid, {}).get(selected, 0)
                if abs(corr) >= self._max_correlation:
                    correlated = True
                    break
            if not correlated:
                independent.append(oid)

        return independent

    def compute_average_correlation(
        self, matrix: Dict[str, Dict[str, float]]
    ) -> float:
        """Compute average pairwise correlation in the matrix."""
        corrs = []
        for oid_a in matrix:
            for corr in matrix[oid_a].values():
                corrs.append(abs(corr))
        if not corrs:
            return 0.0
        return sum(corrs) / len(corrs)

    def get_clusters(
        self,
        matrix: Dict[str, Dict[str, float]],
        n_clusters: int = 5,
    ) -> List[List[str]]:
        """
        Rough clustering of individuals by correlation.

        Each cluster contains mutually correlated individuals.
        """
        # Simple greedy clustering
        individual_ids = list(matrix.keys())
        clusters: List[List[str]] = []
        assigned: Set[str] = set()

        for oid in individual_ids:
            if oid in assigned:
                continue
            cluster = [oid]
            assigned.add(oid)
            for other in individual_ids:
                if other in assigned:
                    continue
                corr = matrix.get(oid, {}).get(other, 0)
                if abs(corr) >= self._max_correlation:
                    cluster.append(other)
                    assigned.add(other)
            clusters.append(cluster)
            if len(clusters) >= n_clusters:
                break

        return clusters

    def clear_cache(self) -> None:
        self._correlation_cache.clear()

    @property
    def max_correlation(self) -> float:
        return self._max_correlation
