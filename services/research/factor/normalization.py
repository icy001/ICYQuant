"""Normalization — eliminate scale effects across factors.

Supports::

    Min-Max, Z-Score, Robust, Rank Normalize

Ensures all factors are on comparable scales before evaluation.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NormalizationMethod(str, Enum):
    """Normalization methods."""

    MIN_MAX = "min_max"
    ZSCORE = "zscore"
    ROBUST = "robust"
    RANK = "rank"


class Normalizer:
    """Factor value normalizer.

    Methods:
    * Min-Max: scale to [0, 1]
    * Z-Score: center at 0 with std=1
    * Robust: median/IQR-based, outlier-resistant
    * Rank: percentile rank normalization
    """

    def __init__(
        self, method: NormalizationMethod = NormalizationMethod.ZSCORE
    ) -> None:
        self._method = method

    @property
    def method(self) -> NormalizationMethod:
        return self._method

    def normalize(
        self,
        values: List[float],
        clip_range: Optional[float] = None,
    ) -> List[float]:
        """Normalize factor values.

        Args:
            values: raw factor values
            clip_range: optional clip at ±N * std (for zscore/robust)

        Returns:
            normalized values
        """
        if not values:
            return []

        if self._method == NormalizationMethod.MIN_MAX:
            return self._min_max(values)
        elif self._method == NormalizationMethod.ZSCORE:
            return self._zscore(values, clip_range)
        elif self._method == NormalizationMethod.ROBUST:
            return self._robust(values, clip_range)
        elif self._method == NormalizationMethod.RANK:
            return self._rank_normalize(values)
        else:
            return list(values)

    def _min_max(self, values: List[float]) -> List[float]:
        min_val = min(values)
        max_val = max(values)
        if max_val == min_val:
            return [0.5] * len(values)
        return [(v - min_val) / (max_val - min_val) for v in values]

    def _zscore(
        self, values: List[float], clip_range: Optional[float] = None
    ) -> List[float]:
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std = variance ** 0.5
        if std == 0:
            return [0.0] * n

        normalized = [(v - mean) / std for v in values]

        if clip_range is not None:
            normalized = [
                max(-clip_range, min(clip_range, v)) for v in normalized
            ]

        return normalized

    def _robust(
        self, values: List[float], clip_range: Optional[float] = None
    ) -> List[float]:
        n = len(values)
        sorted_vals = sorted(values)
        median = sorted_vals[n // 2] if n % 2 == 1 else (
            sorted_vals[n // 2 - 1] + sorted_vals[n // 2]
        ) / 2

        q1_idx = n // 4
        q3_idx = (3 * n) // 4
        q1 = sorted_vals[q1_idx]
        q3 = sorted_vals[q3_idx]
        iqr = q3 - q1
        if iqr == 0:
            return [0.0] * n

        normalized = [(v - median) / iqr for v in values]

        if clip_range is not None:
            normalized = [
                max(-clip_range, min(clip_range, v)) for v in normalized
            ]

        return normalized

    def _rank_normalize(self, values: List[float]) -> List[float]:
        n = len(values)
        indexed = list(enumerate(values))
        indexed.sort(key=lambda x: x[1])

        ranks = [0.0] * n
        for rank, (orig_idx, _) in enumerate(indexed):
            ranks[orig_idx] = (rank + 1) / n

        return ranks

    def stats(
        self, values: List[float]
    ) -> Dict[str, float]:
        """Compute basic statistics of values."""
        if not values:
            return {}
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        return {
            "count": n,
            "mean": mean,
            "std": variance ** 0.5,
            "min": min(values),
            "max": max(values),
        }
