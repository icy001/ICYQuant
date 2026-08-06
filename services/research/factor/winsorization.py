"""Winsorization — outlier treatment for factor values.

Supports::

    MAD (Median Absolute Deviation), Percentile, Sigma Clip

Prevents extreme values from contaminating research results.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class WinsorizationMethod(str, Enum):
    """Winsorization methods."""

    MAD = "mad"            # Median Absolute Deviation
    PERCENTILE = "percentile"  # Percentile-based clipping
    SIGMA_CLIP = "sigma_clip"  # Standard deviation clipping


class Winsorizer:
    """Outlier treatment for factor values.

    Methods:
    * MAD: robust outlier detection using median ± n*MAD
    * Percentile: clip at specified percentiles (e.g., 1%, 99%)
    * Sigma Clip: clip at ±n standard deviations from mean
    """

    def __init__(
        self,
        method: WinsorizationMethod = WinsorizationMethod.MAD,
        limits: Tuple[float, float] = (0.01, 0.99),
        n_sigma: float = 3.0,
        n_mad: float = 5.0,
    ) -> None:
        self._method = method
        self._limits = limits
        self._n_sigma = n_sigma
        self._n_mad = n_mad

    @property
    def method(self) -> WinsorizationMethod:
        return self._method

    def winsorize(self, values: List[float]) -> List[float]:
        """Winsorize factor values.

        Args:
            values: raw factor values

        Returns:
            winsorized values (extreme values clipped)
        """
        if not values:
            return []

        if self._method == WinsorizationMethod.MAD:
            return self._mad_winsorize(values)
        elif self._method == WinsorizationMethod.PERCENTILE:
            return self._percentile_winsorize(values)
        elif self._method == WinsorizationMethod.SIGMA_CLIP:
            return self._sigma_clip(values)
        else:
            return list(values)

    def _mad_winsorize(self, values: List[float]) -> List[float]:
        n = len(values)
        sorted_vals = sorted(values)
        median = sorted_vals[n // 2] if n % 2 == 1 else (
            sorted_vals[n // 2 - 1] + sorted_vals[n // 2]
        ) / 2

        abs_deviations = [abs(v - median) for v in values]
        abs_dev_sorted = sorted(abs_deviations)
        mad = abs_dev_sorted[n // 2] if n % 2 == 1 else (
            abs_dev_sorted[n // 2 - 1] + abs_dev_sorted[n // 2]
        ) / 2

        if mad == 0:
            return list(values)

        lower = median - self._n_mad * mad
        upper = median + self._n_mad * mad

        winsorized = [
            lower if v < lower else (upper if v > upper else v)
            for v in values
        ]

        logger.debug(
            "MAD winsorization: median=%.4f, mad=%.4f, bounds=[%.4f, %.4f]",
            median, mad, lower, upper,
        )
        return winsorized

    def _percentile_winsorize(self, values: List[float]) -> List[float]:
        n = len(values)
        sorted_vals = sorted(values)
        lower_idx = max(0, int(n * self._limits[0]))
        upper_idx = min(n - 1, int(n * self._limits[1]))

        lower = sorted_vals[lower_idx]
        upper = sorted_vals[upper_idx]

        winsorized = [
            lower if v < lower else (upper if v > upper else v)
            for v in values
        ]

        logger.debug(
            "Percentile winsorization: bounds[%.4f, %.4f]=[%.4f, %.4f]",
            self._limits[0], self._limits[1], lower, upper,
        )
        return winsorized

    def _sigma_clip(self, values: List[float]) -> List[float]:
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std = variance ** 0.5

        if std == 0:
            return list(values)

        lower = mean - self._n_sigma * std
        upper = mean + self._n_sigma * std

        winsorized = [
            lower if v < lower else (upper if v > upper else v)
            for v in values
        ]

        logger.debug(
            "Sigma clip: mean=%.4f, std=%.4f, bounds=[%.4f, %.4f]",
            mean, std, lower, upper,
        )
        return winsorized

    def outlier_ratio(self, original: List[float], winsorized: List[float]) -> float:
        """Calculate the proportion of values that were winsorized."""
        if not original:
            return 0.0
        changed = sum(1 for o, w in zip(original, winsorized) if o != w)
        return changed / len(original)
