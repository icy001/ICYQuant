"""Confidence Analyzer – evaluates the confidence level of an AI decision."""

from enum import Enum
from typing import Any, Dict, List, Optional


class ConfidenceLevel(Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"

    @property
    def threshold(self) -> float:
        mapping = {
            ConfidenceLevel.VERY_LOW: 0.0,
            ConfidenceLevel.LOW: 20.0,
            ConfidenceLevel.MODERATE: 40.0,
            ConfidenceLevel.HIGH: 60.0,
            ConfidenceLevel.VERY_HIGH: 80.0,
        }
        return mapping[self]


class ConfidenceAnalyzer:
    """Converts raw probability into a human-readable confidence score and level."""

    LEVEL_THRESHOLDS = [
        (ConfidenceLevel.VERY_HIGH, 80.0),
        (ConfidenceLevel.HIGH, 60.0),
        (ConfidenceLevel.MODERATE, 40.0),
        (ConfidenceLevel.LOW, 20.0),
        (ConfidenceLevel.VERY_LOW, 0.0),
    ]

    def score(self, probability: float) -> float:
        """Convert probability (0.0–1.0) to confidence percentage (0–100).

        Args:
            probability: raw probability in [0, 1].

        Returns:
            Confidence score as percentage, clamped to [0, 100].
        """
        return round(max(0.0, min(1.0, probability)) * 100, 2)

    def level(self, probability: float) -> ConfidenceLevel:
        """Map probability to a qualitative confidence level."""
        pct = self.score(probability)
        for level, threshold in self.LEVEL_THRESHOLDS:
            if pct >= threshold:
                return level
        return ConfidenceLevel.VERY_LOW

    def is_actionable(self, probability: float, min_confidence: float = 60.0) -> bool:
        """Check if the confidence is high enough to act on."""
        return self.score(probability) >= min_confidence

    def analyze(self, probability: float) -> Dict[str, Any]:
        """Full confidence analysis."""
        conf_score = self.score(probability)
        conf_level = self.level(probability)
        return {
            "confidence_score": conf_score,
            "confidence_level": conf_level.value,
            "actionable": self.is_actionable(probability),
        }
