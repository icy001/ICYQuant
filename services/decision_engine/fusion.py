from typing import Dict, List, Optional


class SignalFusionEngine:
    """Combines multiple signals from different sources into a unified score.

    Supports equal-weight, weighted, and custom fusion strategies.
    """

    def __init__(self, default_weights: Optional[Dict[str, float]] = None):
        self.default_weights = default_weights or {}

    def combine(self, signals: List[float]) -> float:
        """Simple equal-weight fusion of a list of signal values.

        Args:
            signals: List of numerical signal values.

        Returns:
            The arithmetic mean of all signals.
        """
        if not signals:
            return 0.0
        return sum(signals) / len(signals)

    def combine_weighted(
        self,
        signals: Dict[str, float],
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Weighted fusion of named signals.

        Args:
            signals: Dict mapping signal name to its value.
            weights: Optional dict mapping signal name to weight.
                     Falls back to default_weights and then equal weight.

        Returns:
            Weighted average score.
        """
        if not signals:
            return 0.0

        w = weights or self.default_weights
        total = 0.0
        total_weight = 0.0

        for name, value in signals.items():
            weight = w.get(name, 1.0)
            total += value * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0
        return total / total_weight

    def fuse_with_confidence(
        self,
        signals: Dict[str, float],
        confidences: Dict[str, float],
    ) -> Dict[str, float]:
        """Fuse signals using confidence scores as weights.

        Args:
            signals: Dict of signal name -> signal value.
            confidences: Dict of signal name -> confidence (0-1).

        Returns:
            Dict with 'score' and 'confidence'.
        """
        if not signals:
            return {"score": 0.0, "confidence": 0.0}

        total = 0.0
        total_conf = 0.0

        for name, value in signals.items():
            conf = confidences.get(name, 0.5)
            total += value * conf
            total_conf += conf

        avg_conf = total_conf / len(signals) if signals else 0.0
        score = total / total_conf if total_conf > 0 else 0.0

        return {"score": score, "confidence": min(avg_conf, 1.0)}
