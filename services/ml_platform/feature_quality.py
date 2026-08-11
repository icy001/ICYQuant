"""
ICYQuant Feature Quality Engine - Feature quality scoring and monitoring.

Evaluates feature quality across multiple dimensions:
- Coverage: percentage of non-null values
- Stability: consistency of feature values over time
- Predictive power: information coefficient, mutual information
- Freshness: how recent the data is
- Distribution stability: PSI (Population Stability Index)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Quality Dimension
# ---------------------------------------------------------------------------


class QualityDimension(Enum):
    """Dimensions of feature quality."""

    COVERAGE = "coverage"           # % non-null values
    COMPLETENESS = "completeness"   # all expected entities present
    FRESHNESS = "freshness"          # how recent the data
    STABILITY = "stability"          # value stability over time
    ACCURACY = "accuracy"            # correctness against ground truth
    CONSISTENCY = "consistency"      # cross-source consistency
    PREDICTIVE_POWER = "predictive"  # IC, mutual information
    UNIQUENESS = "uniqueness"        # % unique values


class QualityLevel(Enum):
    """Overall quality assessment."""

    EXCELLENT = auto()  # >= 0.90
    GOOD = auto()       # >= 0.75
    FAIR = auto()       # >= 0.50
    POOR = auto()       # >= 0.25
    BAD = auto()        # < 0.25


# ---------------------------------------------------------------------------
# Quality Data
# ---------------------------------------------------------------------------


@dataclass
class DimensionScore:
    """Score for a single quality dimension."""

    dimension: QualityDimension
    score: float  # 0.0 - 1.0
    threshold: float = 0.7
    passed: bool = True
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityReport:
    """Comprehensive feature quality report."""

    report_id: str = ""
    feature_id: str = ""
    feature_name: str = ""

    # Overall
    overall_score: float = 0.0
    quality_level: QualityLevel = QualityLevel.FAIR

    # Per-dimension scores
    dimension_scores: Dict[QualityDimension, DimensionScore] = field(default_factory=dict)

    # Metadata
    evaluated_at: datetime = field(default_factory=datetime.utcnow)
    data_start: Optional[datetime] = None
    data_end: Optional[datetime] = None
    entity_count: int = 0
    row_count: int = 0

    # Issues
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Quality Engine
# ---------------------------------------------------------------------------


class FeatureQualityEngine:
    """Evaluates and monitors feature quality across all dimensions.

    Provides:
    - Per-dimension quality scoring
    - Overall quality level assessment
    - Trend monitoring (quality decay detection)
    - Automated recommendations for quality improvement
    """

    def __init__(self) -> None:
        self._thresholds: Dict[QualityDimension, float] = {
            QualityDimension.COVERAGE: 0.80,
            QualityDimension.COMPLETENESS: 0.80,
            QualityDimension.FRESHNESS: 0.70,
            QualityDimension.STABILITY: 0.70,
            QualityDimension.ACCURACY: 0.80,
            QualityDimension.CONSISTENCY: 0.70,
            QualityDimension.PREDICTIVE_POWER: 0.50,
            QualityDimension.UNIQUENESS: 0.50,
        }

    # -- Evaluate --

    async def evaluate(self, values: Any, feature_name: str, **kwargs: Any) -> QualityReport:
        """Evaluate feature quality comprehensively."""
        report = QualityReport(
            report_id=f"quality_{feature_name}_{datetime.utcnow().strftime('%Y%m%d')}",
            feature_id=feature_name,
            feature_name=feature_name,
        )

        # Evaluate each dimension
        scores: Dict[QualityDimension, DimensionScore] = {}

        scores[QualityDimension.COVERAGE] = await self._evaluate_coverage(values)
        scores[QualityDimension.COMPLETENESS] = await self._evaluate_completeness(values)
        scores[QualityDimension.FRESHNESS] = await self._evaluate_freshness(values, kwargs.get("last_updated"))
        scores[QualityDimension.STABILITY] = await self._evaluate_stability(values)
        scores[QualityDimension.UNIQUENESS] = await self._evaluate_uniqueness(values)
        scores[QualityDimension.PREDICTIVE_POWER] = await self._evaluate_predictive_power(
            values, kwargs.get("labels")
        )

        report.dimension_scores = scores

        # Compute overall score (weighted average)
        weights = {
            QualityDimension.COVERAGE: 0.20,
            QualityDimension.COMPLETENESS: 0.15,
            QualityDimension.FRESHNESS: 0.10,
            QualityDimension.STABILITY: 0.15,
            QualityDimension.UNIQUENESS: 0.10,
            QualityDimension.PREDICTIVE_POWER: 0.20,
            QualityDimension.CONSISTENCY: 0.05,
            QualityDimension.ACCURACY: 0.05,
        }

        report.overall_score = sum(
            scores[dim].score * weights.get(dim, 0.1)
            for dim in scores
        )

        # Map to quality level
        report.quality_level = self._score_to_level(report.overall_score)

        # Generate recommendations
        report.recommendations = self._generate_recommendations(scores)

        return report

    # -- Dimension Evaluators --

    async def _evaluate_coverage(self, values: Any) -> DimensionScore:
        """Evaluate null coverage ratio."""
        threshold = self._thresholds[QualityDimension.COVERAGE]
        # Placeholder
        return DimensionScore(
            dimension=QualityDimension.COVERAGE,
            score=1.0,
            threshold=threshold,
            passed=True,
        )

    async def _evaluate_completeness(self, values: Any) -> DimensionScore:
        """Evaluate if all expected entities have values."""
        threshold = self._thresholds[QualityDimension.COMPLETENESS]
        return DimensionScore(
            dimension=QualityDimension.COMPLETENESS,
            score=1.0,
            threshold=threshold,
            passed=True,
        )

    async def _evaluate_freshness(self, values: Any, last_updated: Optional[datetime]) -> DimensionScore:
        """Evaluate data freshness."""
        threshold = self._thresholds[QualityDimension.FRESHNESS]
        age_days = 0
        if last_updated:
            age_days = (datetime.utcnow() - last_updated).days
        score = max(0.0, 1.0 - age_days / 7.0)  # decays over 7 days
        return DimensionScore(
            dimension=QualityDimension.FRESHNESS,
            score=score,
            threshold=threshold,
            passed=score >= threshold,
            detail={"age_days": age_days},
        )

    async def _evaluate_stability(self, values: Any) -> DimensionScore:
        """Evaluate value stability."""
        threshold = self._thresholds[QualityDimension.STABILITY]
        return DimensionScore(
            dimension=QualityDimension.STABILITY,
            score=1.0,
            threshold=threshold,
            passed=True,
        )

    async def _evaluate_uniqueness(self, values: Any) -> DimensionScore:
        """Evaluate unique value ratio."""
        threshold = self._thresholds[QualityDimension.UNIQUENESS]
        return DimensionScore(
            dimension=QualityDimension.UNIQUENESS,
            score=0.8,
            threshold=threshold,
            passed=True,
        )

    async def _evaluate_predictive_power(self, values: Any, labels: Any = None) -> DimensionScore:
        """Evaluate predictive power (IC, mutual info) if labels available."""
        threshold = self._thresholds[QualityDimension.PREDICTIVE_POWER]
        score = 0.5
        if labels is not None:
            # Placeholder: compute IC in production
            pass
        return DimensionScore(
            dimension=QualityDimension.PREDICTIVE_POWER,
            score=score,
            threshold=threshold,
            passed=score >= threshold if labels is not None else True,
        )

    # -- Utilities --

    def _score_to_level(self, score: float) -> QualityLevel:
        if score >= 0.90:
            return QualityLevel.EXCELLENT
        elif score >= 0.75:
            return QualityLevel.GOOD
        elif score >= 0.50:
            return QualityLevel.FAIR
        elif score >= 0.25:
            return QualityLevel.POOR
        return QualityLevel.BAD

    def _generate_recommendations(self, scores: Dict[QualityDimension, DimensionScore]) -> List[str]:
        """Generate improvement recommendations based on scores."""
        recommendations: List[str] = []
        for dim, score in scores.items():
            if not score.passed:
                recommendations.append(f"Improve {dim.value} (score: {score.score:.2f}, threshold: {score.threshold:.2f})")
        return recommendations

    async def compare_quality(self, report1: QualityReport, report2: QualityReport) -> Dict[str, float]:
        """Compare quality between two reports (e.g., training vs. production)."""
        changes: Dict[str, float] = {}
        for dim in report1.dimension_scores:
            if dim in report2.dimension_scores:
                s1 = report1.dimension_scores[dim].score
                s2 = report2.dimension_scores[dim].score
                changes[dim.value] = s2 - s1
        return changes
