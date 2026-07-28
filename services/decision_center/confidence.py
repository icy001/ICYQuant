"""Confidence Aggregator – computes overall confidence across all agent decisions."""

from typing import Dict, List

from .collector import DecisionPackage


class ConfidenceAggregator:
    """Aggregates confidence scores from multiple decisions into one overall confidence."""

    def aggregate(self, decisions: List[DecisionPackage]) -> float:
        """Simple average of all confidences.

        Args:
            decisions: list of DecisionPackages.

        Returns:
            Average confidence in [0, 1].
        """
        if not decisions:
            return 0.0
        return sum(d.confidence for d in decisions) / len(decisions)

    def weighted_aggregate(
        self,
        decisions: List[DecisionPackage],
        weights: Dict[str, float],
    ) -> float:
        """Weighted average by source weights.

        Args:
            decisions: list of DecisionPackages.
            weights: source → weight mapping.

        Returns:
            Weighted average confidence.
        """
        if not decisions:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0
        for d in decisions:
            w = weights.get(d.source, 1.0)
            weighted_sum += d.confidence * w
            total_weight += w

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def harmonic_mean(self, decisions: List[DecisionPackage]) -> float:
        """Harmonic mean of confidences — penalizes low-confidence outliers.

        Args:
            decisions: list of DecisionPackages.

        Returns:
            Harmonic mean confidence.
        """
        if not decisions:
            return 0.0
        confs = [d.confidence for d in decisions if d.confidence > 0]
        if not confs:
            return 0.0
        return len(confs) / sum(1.0 / c for c in confs)

    def aggregate_stats(self, decisions: List[DecisionPackage]) -> Dict[str, float]:
        """Return aggregate statistics: mean, min, max, harmonic_mean, count."""
        if not decisions:
            return {"mean": 0.0, "min": 0.0, "max": 0.0, "harmonic_mean": 0.0, "count": 0}

        confs = [d.confidence for d in decisions]
        return {
            "mean": self.aggregate(decisions),
            "min": min(confs),
            "max": max(confs),
            "harmonic_mean": self.harmonic_mean(decisions),
            "count": len(confs),
        }
