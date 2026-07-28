"""Feature Importance Analyzer – ranks input features by their contribution."""

from typing import Dict, List, Tuple


class FeatureImportanceAnalyzer:
    """Ranks model features by importance scores."""

    def rank(self, features: Dict[str, float]) -> List[Tuple[str, float]]:
        """Sort features by importance in descending order.

        Args:
            features: feature_name -> importance_score mapping.

        Returns:
            Sorted list of (feature_name, importance) tuples.
        """
        if not features:
            return []
        return sorted(features.items(), key=lambda x: x[1], reverse=True)

    def top_features(self, features: Dict[str, float], n: int = 5) -> List[Tuple[str, float]]:
        """Return the top-N most important features."""
        return self.rank(features)[:n]

    def cumulative_importance(self, features: Dict[str, float], threshold: float = 0.80) -> List[Tuple[str, float]]:
        """Return the minimal set of features that explain at least `threshold` of total importance.

        Useful for identifying which features drive most of the model's decision.
        """
        ranked = self.rank(features)
        total = sum(v for _, v in ranked)
        if total == 0:
            return []
        cumulative = 0.0
        result: List[Tuple[str, float]] = []
        for name, val in ranked:
            cumulative += val
            result.append((name, val))
            if cumulative / total >= threshold:
                break
        return result
