"""
Experiment statistics collection.

Collects and aggregates metrics for experiment
variants including sample sizes, conversion
rates, and domain-specific KPIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VariantStats:
    """
    Statistics for a single experiment variant.

    Attributes:
        variant_id: Variant identifier.
        sample_size: Number of observations.
        conversions: Number of successful conversions.
        conversion_rate: Conversion rate (0-1).
        total_value: Sum of metric values.
        average_value: Average metric value.
        variance: Variance of metric values.
        custom_metrics: Additional custom metrics.
    """

    variant_id: str = ""
    sample_size: int = 0
    conversions: int = 0
    conversion_rate: float = 0.0
    total_value: float = 0.0
    average_value: float = 0.0
    variance: float = 0.0
    custom_metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "variant_id": self.variant_id,
            "sample_size": self.sample_size,
            "conversions": self.conversions,
            "conversion_rate": self.conversion_rate,
            "total_value": self.total_value,
            "average_value": self.average_value,
            "variance": self.variance,
            "custom_metrics": self.custom_metrics,
        }


class StatisticsCollector:
    """
    Collects experiment statistics per variant.

    Aggregates observations and computes
    conversion rates, averages, and variances
    for statistical analysis.

    Usage:
        collector = StatisticsCollector()
        collector.record("control", value=1.0, converted=True)
        collector.record("treatment", value=1.5, converted=True)
        stats = collector.get_stats("control")
    """

    def __init__(self) -> None:
        """Initialize the statistics collector."""
        self._observations: Dict[str, List[float]] = {}
        self._conversions: Dict[str, int] = {}
        self._custom_metrics: Dict[str, Dict[str, List[float]]] = {}

    def record(
        self,
        variant_id: str,
        value: float = 1.0,
        converted: bool = False,
        custom_metrics: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Record an observation for a variant.

        Args:
            variant_id: Variant identifier.
            value: Metric value.
            converted: Whether a conversion occurred.
            custom_metrics: Additional metric values.
        """
        if variant_id not in self._observations:
            self._observations[variant_id] = []
            self._conversions[variant_id] = 0
            self._custom_metrics[variant_id] = {}

        self._observations[variant_id].append(value)
        if converted:
            self._conversions[variant_id] += 1

        if custom_metrics:
            for key, metric_value in custom_metrics.items():
                if key not in self._custom_metrics[variant_id]:
                    self._custom_metrics[variant_id][key] = []
                self._custom_metrics[variant_id][key].append(metric_value)

    def get_stats(self, variant_id: str) -> VariantStats:
        """
        Get statistics for a variant.

        Args:
            variant_id: Variant identifier.

        Returns:
            VariantStats with computed metrics.
        """
        obs = self._observations.get(variant_id, [])
        conv = self._conversions.get(variant_id, 0)

        n = len(obs)
        if n == 0:
            return VariantStats(variant_id=variant_id)

        total = sum(obs)
        avg = total / n

        # Compute variance
        if n > 1:
            variance = sum((x - avg) ** 2 for x in obs) / (n - 1)
        else:
            variance = 0.0

        # Custom metric averages
        custom = {}
        for key, values in self._custom_metrics.get(variant_id, {}).items():
            if values:
                custom[key] = sum(values) / len(values)

        return VariantStats(
            variant_id=variant_id,
            sample_size=n,
            conversions=conv,
            conversion_rate=conv / n if n > 0 else 0.0,
            total_value=total,
            average_value=avg,
            variance=variance,
            custom_metrics=custom,
        )

    def get_all_stats(self) -> Dict[str, VariantStats]:
        """Get statistics for all variants."""
        return {
            vid: self.get_stats(vid)
            for vid in self._observations
        }

    def reset(self, variant_id: Optional[str] = None) -> None:
        """Reset statistics."""
        if variant_id:
            self._observations.pop(variant_id, None)
            self._conversions.pop(variant_id, None)
            self._custom_metrics.pop(variant_id, None)
        else:
            self._observations.clear()
            self._conversions.clear()
            self._custom_metrics.clear()
