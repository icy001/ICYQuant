"""
ICYQuant Feature Drift - Feature-level distribution drift detection.

Monitors individual feature distributions for shifts that could
degrade model performance. Tracks per-feature drift scores and
maintains drift history for trend analysis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FeatureDriftMethod(Enum):
    """Methods for feature drift detection."""

    PSI = "psi"
    KS_TEST = "ks_test"
    JS_DIVERGENCE = "js_divergence"
    MEAN_SHIFT = "mean_shift"
    VARIANCE_SHIFT = "variance_shift"
    PERCENTILE_SHIFT = "percentile_shift"


@dataclass
class FeatureDriftResult:
    """Per-feature drift result."""

    feature_id: str = ""
    feature_name: str = ""

    # Drift scores
    psi: float = 0.0
    ks_statistic: float = 0.0
    mean_shift_ratio: float = 0.0   # (current_mean - ref_mean) / ref_std
    variance_ratio: float = 1.0     # current_var / ref_var

    # Overall
    drift_score: float = 0.0
    significant: bool = False
    severity: str = "none"

    # Reference stats
    ref_mean: float = 0.0
    ref_std: float = 0.0
    ref_median: float = 0.0
    ref_p5: float = 0.0
    ref_p95: float = 0.0

    # Current stats
    cur_mean: float = 0.0
    cur_std: float = 0.0
    cur_median: float = 0.0
    cur_p5: float = 0.0
    cur_p95: float = 0.0

    # Metadata
    checked_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FeatureDriftSummary:
    """Summary of feature drift across all features."""

    total_features: int = 0
    drifted_features: int = 0
    overall_drift_score: float = 0.0
    max_drift_score: float = 0.0
    max_drifted_feature: str = ""
    per_feature_results: Dict[str, FeatureDriftResult] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)


class FeatureDriftDetector:
    """Detects distribution shifts in individual features.

    Tracks:
    - PSI per feature
    - Mean shift (z-score of difference)
    - Variance stability
    - Percentile shifts
    - Long-term drift trends
    """

    def __init__(self, threshold: float = 0.05) -> None:
        self.threshold = threshold
        self._drift_history: Dict[str, List[FeatureDriftResult]] = {}

    # -- Detect --

    async def detect(
        self,
        reference_data: Any,
        current_data: Any,
        feature_names: Optional[List[str]] = None,
    ) -> FeatureDriftSummary:
        """Detect feature-level drift.

        Args:
            reference_data: Training/reference feature matrix.
            current_data: Current production feature matrix.
            feature_names: Feature names.

        Returns:
            FeatureDriftSummary with per-feature results.
        """
        summary = FeatureDriftSummary(
            total_features=len(feature_names) if feature_names else 0,
        )

        if feature_names:
            for i, name in enumerate(feature_names):
                result = await self._check_feature(name, i, reference_data, current_data)
                summary.per_feature_results[name] = result

                if result.significant:
                    summary.drifted_features += 1

                if result.drift_score > summary.max_drift_score:
                    summary.max_drift_score = result.drift_score
                    summary.max_drifted_feature = name

            # Track history
            for name, result in summary.per_feature_results.items():
                if name not in self._drift_history:
                    self._drift_history[name] = []
                self._drift_history[name].append(result)

        if summary.total_features > 0:
            summary.overall_drift_score = sum(
                r.drift_score for r in summary.per_feature_results.values()
            ) / summary.total_features

        logger.info("Feature drift: overall=%.4f, drifted=%d/%d, max=%s(%.4f)",
                     summary.overall_drift_score, summary.drifted_features,
                     summary.total_features, summary.max_drifted_feature, summary.max_drift_score)

        return summary

    async def _check_feature(
        self, name: str, index: int, reference: Any, current: Any,
    ) -> FeatureDriftResult:
        """Check drift for a single feature."""
        result = FeatureDriftResult(
            feature_id=name,
            feature_name=name,
        )
        # Placeholder: actual per-feature computation
        return result

    # -- Trending --

    def get_drift_trend(self, feature_name: str, window: int = 30) -> List[float]:
        """Get drift score trend for a feature.

        Returns:
            List of drift scores over time.
        """
        history = self._drift_history.get(feature_name, [])
        return [h.drift_score for h in history[-window:]]

    def get_most_drifted_features(self, top_n: int = 10) -> List[tuple]:
        """Get features with the highest recent drift."""
        scores: List[tuple] = []
        for name, history in self._drift_history.items():
            if history:
                scores.append((name, history[-1].drift_score))
        return sorted(scores, key=lambda x: x[1], reverse=True)[:top_n]
