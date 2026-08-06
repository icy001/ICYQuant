"""Standardization — transform factors to mean=0, std=1.

Standardized factors are comparable and suitable for multi-factor
combination, portfolio construction, and risk modeling.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Standardizer:
    """Factor value standardizer.

    Transforms factor values to have mean=0 and standard deviation=1,
    making them directly comparable and combinable.
    """

    def __init__(self, cross_sectional: bool = True) -> None:
        self._cross_sectional = cross_sectional

    @property
    def cross_sectional(self) -> bool:
        return self._cross_sectional

    def standardize(
        self,
        values: List[float],
        weights: Optional[List[float]] = None,
    ) -> List[float]:
        """Standardize factor values to mean=0, std=1.

        Args:
            values: raw factor values
            weights: optional sample weights for weighted standardization

        Returns:
            standardized values
        """
        if not values:
            return []

        n = len(values)

        if weights and len(weights) == n:
            total_weight = sum(weights)
            if total_weight == 0:
                return [0.0] * n
            mean = sum(v * w for v, w in zip(values, weights)) / total_weight
            variance = sum(
                w * (v - mean) ** 2 for v, w in zip(values, weights)
            ) / total_weight
        else:
            mean = sum(values) / n
            variance = sum((v - mean) ** 2 for v in values) / n

        std = variance ** 0.5
        if std == 0:
            return [0.0] * n

        return [(v - mean) / std for v in values]

    def standardize_cross_sectional(
        self,
        cross_sections: Dict[str, List[float]],
    ) -> Dict[str, List[float]]:
        """Standardize each cross-section independently.

        Args:
            cross_sections: date → values mapping

        Returns:
            date → standardized values mapping
        """
        result: Dict[str, List[float]] = {}
        for date_key, values in cross_sections.items():
            result[date_key] = self.standardize(values)
        return result

    def stats(self, values: List[float]) -> Dict[str, float]:
        """Verify standardization: should have mean≈0, std≈1."""
        if not values:
            return {}
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        return {
            "mean": mean,
            "std": variance ** 0.5,
            "min": min(values),
            "max": max(values),
        }
