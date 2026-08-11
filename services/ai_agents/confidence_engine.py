"""
ICYQuant Confidence Engine — confidence scoring for agent outputs.

Calculates confidence scores for agent decisions, research findings,
and strategy recommendations based on evidence quality, data recency,
methodology rigor, and cross-validation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ConfidenceTier(str, Enum):
    VERY_HIGH = "very_high"    # >90%
    HIGH = "high"              # 75-90%
    MEDIUM = "medium"          # 50-75%
    LOW = "low"               # 25-50%
    VERY_LOW = "very_low"     # <25%


@dataclass
class ConfidenceFactors:
    """Factors contributing to a confidence score."""
    evidence_quality: float = 0.5     # Quality and quantity of evidence
    data_recency: float = 0.5         # How recent/relevant the data is
    methodology_rigor: float = 0.5    # Soundness of methodology
    cross_validation: float = 0.5     # Cross-validation results
    agent_expertise: float = 0.5      # Expertise of the agent making the claim
    consensus_alignment: float = 0.5  # Agreement with other agents
    backtest_robustness: float = 0.5  # Out-of-sample performance
    sensitivity: float = 0.5          # Robustness to parameter changes

    def to_dict(self) -> dict[str, float]:
        return {
            "evidence_quality": self.evidence_quality,
            "data_recency": self.data_recency,
            "methodology_rigor": self.methodology_rigor,
            "cross_validation": self.cross_validation,
            "agent_expertise": self.agent_expertise,
            "consensus_alignment": self.consensus_alignment,
            "backtest_robustness": self.backtest_robustness,
            "sensitivity": self.sensitivity,
        }


@dataclass
class ConfidenceScore:
    """A confidence score with contributing factors."""
    score: float = 0.0                 # 0.0 - 1.0
    tier: ConfidenceTier = ConfidenceTier.VERY_LOW
    factors: ConfidenceFactors = field(default_factory=ConfidenceFactors)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


# Default factor weights for overall confidence calculation
DEFAULT_WEIGHTS = {
    "evidence_quality": 0.20,
    "data_recency": 0.10,
    "methodology_rigor": 0.15,
    "cross_validation": 0.15,
    "agent_expertise": 0.10,
    "consensus_alignment": 0.10,
    "backtest_robustness": 0.15,
    "sensitivity": 0.05,
}


class ConfidenceEngine:
    """Calculates confidence scores for multi-agent outputs.

    Computes weighted confidence from multiple factors:
        - Evidence quality and quantity
        - Data recency and relevance
        - Methodology rigor and soundness
        - Cross-validation and out-of-sample testing
        - Agent expertise and track record
        - Consensus alignment across agents
        - Backtest robustness
        - Parameter sensitivity

    Generates warnings when confidence is low and recommendations
    for improving score.
    """

    def __init__(self, weights: Optional[dict[str, float]] = None) -> None:
        self._weights = weights or DEFAULT_WEIGHTS
        self._total_scores = 0

    def calculate(self, factors: ConfidenceFactors) -> ConfidenceScore:
        """Calculate a confidence score from factor values."""
        self._total_scores += 1

        factor_dict = factors.to_dict()
        weighted_sum = 0.0
        total_weight = 0.0

        for factor_name, factor_value in factor_dict.items():
            weight = self._weights.get(factor_name, 0.0)
            weighted_sum += factor_value * weight
            total_weight += weight

        score = weighted_sum / total_weight if total_weight > 0 else 0.0
        score = max(0.0, min(1.0, score))

        tier = self._score_to_tier(score)
        warnings = self._generate_warnings(factors, score)
        recommendations = self._generate_recommendations(factors)

        return ConfidenceScore(
            score=score,
            tier=tier,
            factors=factors,
            warnings=warnings,
            recommendations=recommendations,
        )

    def quick_score(self, evidence_quality: float = 0.5,
                    agent_confidence: float = 0.5,
                    agreement_count: int = 0,
                    total_agents: int = 1) -> float:
        """Quick confidence estimate without full factor analysis."""
        eq = evidence_quality * 0.4
        ac = agent_confidence * 0.3
        ca = (agreement_count / max(total_agents, 1)) * 0.3
        score = eq + ac + ca
        return max(0.0, min(1.0, score))

    def merge_scores(self, scores: list[ConfidenceScore]) -> ConfidenceScore:
        """Merge multiple confidence scores into a combined score."""
        if not scores:
            return ConfidenceScore()

        avg_score = sum(s.score for s in scores) / len(scores)
        all_warnings = list(set(w for s in scores for w in s.warnings))
        all_recs = list(set(r for s in scores for r in s.recommendations))

        # Average the factors
        merged_factors = ConfidenceFactors()
        factor_names = merged_factors.to_dict().keys()
        for name in factor_names:
            values = [getattr(s.factors, name, 0.5) for s in scores]
            setattr(merged_factors, name, sum(values) / len(values))

        return ConfidenceScore(
            score=avg_score,
            tier=self._score_to_tier(avg_score),
            factors=merged_factors,
            warnings=all_warnings,
            recommendations=all_recs,
        )

    def _score_to_tier(self, score: float) -> ConfidenceTier:
        if score >= 0.9:
            return ConfidenceTier.VERY_HIGH
        if score >= 0.75:
            return ConfidenceTier.HIGH
        if score >= 0.5:
            return ConfidenceTier.MEDIUM
        if score >= 0.25:
            return ConfidenceTier.LOW
        return ConfidenceTier.VERY_LOW

    def _generate_warnings(self, factors: ConfidenceFactors, score: float) -> list[str]:
        """Generate warnings for low-factor values."""
        warnings = []
        if factors.evidence_quality < 0.3:
            warnings.append("Insufficient evidence — conclusions may be unreliable")
        if factors.data_recency < 0.3:
            warnings.append("Data may be stale — consider refreshing data sources")
        if factors.cross_validation < 0.3:
            warnings.append("Limited cross-validation — risk of overfitting")
        if factors.backtest_robustness < 0.3:
            warnings.append("Weak backtest performance — strategy may not generalize")
        if score < 0.3:
            warnings.append("Very low overall confidence — treat as experimental only")
        return warnings

    def _generate_recommendations(self, factors: ConfidenceFactors) -> list[str]:
        """Generate recommendations to improve confidence."""
        recs = []
        if factors.evidence_quality < 0.5:
            recs.append("Gather additional evidence from independent sources")
        if factors.cross_validation < 0.5:
            recs.append("Perform out-of-sample cross-validation")
        if factors.sensitivity < 0.5:
            recs.append("Conduct sensitivity analysis on key parameters")
        if factors.backtest_robustness < 0.5:
            recs.append("Test strategy on extended historical periods")
        return recs

    @property
    def total_scores(self) -> int:
        return self._total_scores
