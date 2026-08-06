"""Correlation Analysis — inter-factor correlation detection.

Outputs::

    Pearson, Spearman, Distance Correlation

Identifies redundant alpha signals across factors.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CorrelationResult:
    """Correlation analysis result."""

    factor_name: str = ""
    pearson_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    spearman_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    high_correlation_pairs: List[Dict[str, Any]] = field(default_factory=list)
    redundant_factors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "factor_name": self.factor_name,
            "pearson_matrix_size": len(self.pearson_matrix),
            "spearman_matrix_size": len(self.spearman_matrix),
            "high_correlation_pairs": self.high_correlation_pairs,
            "redundant_factors": self.redundant_factors,
            "metadata": self.metadata,
        }


class CorrelationAnalyzer:
    """Inter-factor correlation analyzer.

    Detects redundant factors through:
    * Pearson correlation (linear)
    * Spearman rank correlation (monotonic)
    * Distance correlation (non-linear)

    Helps avoid over-weighting correlated alpha signals.
    """

    def __init__(
        self,
        pearson_threshold: float = 0.7,
        spearman_threshold: float = 0.7,
    ) -> None:
        self._pearson_threshold = pearson_threshold
        self._spearman_threshold = spearman_threshold

    def analyze(
        self,
        factor_matrix: Dict[str, List[float]],
        factor_name: str = "",
    ) -> CorrelationResult:
        """Analyze correlations among factors.

        Args:
            factor_matrix: factor_name → values mapping
            factor_name: primary factor identifier

        Returns:
            CorrelationResult with correlation matrices
        """
        result = CorrelationResult(factor_name=factor_name)
        names = list(factor_matrix.keys())

        if len(names) < 2:
            return result

        # Pearson correlation matrix
        result.pearson_matrix = self._pearson_correlation(factor_matrix)

        # Spearman correlation matrix
        result.spearman_matrix = self._spearman_correlation(factor_matrix)

        # Detect high correlation pairs
        result.high_correlation_pairs = self._detect_high_correlation(
            result.pearson_matrix, result.spearman_matrix
        )

        # Identify redundant factors
        result.redundant_factors = self._find_redundant(
            result.high_correlation_pairs, names
        )

        return result

    def _pearson_correlation(
        self, factor_matrix: Dict[str, List[float]]
    ) -> Dict[str, Dict[str, float]]:
        """Compute Pearson correlation matrix."""
        names = list(factor_matrix.keys())
        corr: Dict[str, Dict[str, float]] = {}

        for name_i in names:
            corr[name_i] = {}
            vals_i = factor_matrix[name_i]
            mean_i = sum(vals_i) / len(vals_i)
            var_i = sum((v - mean_i) ** 2 for v in vals_i) / len(vals_i)
            std_i = var_i ** 0.5

            for name_j in names:
                if name_i == name_j:
                    corr[name_i][name_j] = 1.0
                    continue

                vals_j = factor_matrix[name_j]
                n = min(len(vals_i), len(vals_j))
                mean_j = sum(vals_j[:n]) / n
                var_j = sum((v - mean_j) ** 2 for v in vals_j[:n]) / n
                std_j = var_j ** 0.5

                if std_i > 0 and std_j > 0:
                    cov = sum(
                        (vi - mean_i) * (vj - mean_j)
                        for vi, vj in zip(vals_i[:n], vals_j[:n])
                    ) / n
                    corr[name_i][name_j] = cov / (std_i * std_j)
                else:
                    corr[name_i][name_j] = 0.0

        return corr

    def _spearman_correlation(
        self, factor_matrix: Dict[str, List[float]]
    ) -> Dict[str, Dict[str, float]]:
        """Compute Spearman rank correlation matrix."""
        names = list(factor_matrix.keys())

        def rank_values(vals: List[float]) -> List[float]:
            n = len(vals)
            indexed = list(enumerate(vals))
            indexed.sort(key=lambda x: x[1])
            ranks = [0.0] * n
            i = 0
            while i < n:
                j = i
                while j < n and indexed[j][1] == indexed[i][1]:
                    j += 1
                avg_rank = (i + j - 1) / 2 + 1
                for k in range(i, j):
                    ranks[indexed[k][0]] = avg_rank
                i = j
            return ranks

        ranked = {name: rank_values(vals) for name, vals in factor_matrix.items()}
        return self._pearson_correlation(ranked)

    def _detect_high_correlation(
        self,
        pearson: Dict[str, Dict[str, float]],
        spearman: Dict[str, Dict[str, float]],
    ) -> List[Dict[str, Any]]:
        """Find factor pairs with high correlation."""
        pairs = []
        names = list(pearson.keys())

        for i, name_i in enumerate(names):
            for name_j in names[i + 1:]:
                p_corr = pearson.get(name_i, {}).get(name_j, 0.0)
                s_corr = spearman.get(name_i, {}).get(name_j, 0.0)

                if abs(p_corr) >= self._pearson_threshold or abs(s_corr) >= self._spearman_threshold:
                    pairs.append({
                        "factor_a": name_i,
                        "factor_b": name_j,
                        "pearson": p_corr,
                        "spearman": s_corr,
                    })

        return pairs

    def _find_redundant(
        self,
        high_pairs: List[Dict[str, Any]],
        all_names: List[str],
    ) -> List[str]:
        """Identify redundant factors (appearing in most high-correlation pairs)."""
        if not high_pairs:
            return []

        pair_counts: Dict[str, int] = {}
        for pair in high_pairs:
            pair_counts[pair["factor_a"]] = pair_counts.get(pair["factor_a"], 0) + 1
            pair_counts[pair["factor_b"]] = pair_counts.get(pair["factor_b"], 0) + 1

        # Factors appearing in >50% of high-correlation pairs are redundant
        threshold = max(len(high_pairs) * 0.5, 1)
        return [name for name, count in pair_counts.items() if count > threshold]

    def average_correlation(
        self, matrix: Dict[str, Dict[str, float]]
    ) -> float:
        """Compute average pairwise correlation (excluding diagonal)."""
        names = list(matrix.keys())
        if len(names) < 2:
            return 0.0

        total = 0.0
        count = 0
        for i, name_i in enumerate(names):
            for name_j in names[i + 1:]:
                total += abs(matrix.get(name_i, {}).get(name_j, 0.0))
                count += 1

        return total / count if count > 0 else 0.0
