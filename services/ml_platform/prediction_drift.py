"""
ICYQuant Prediction Drift - Model prediction distribution drift detection.

Monitors shifts in model output distributions, which is often the
first indicator of model degradation or market regime change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PredictionDriftResult:
    """Result of prediction drift detection."""

    # Drift metrics
    psi: float = 0.0
    ks_statistic: float = 0.0
    js_divergence: float = 0.0
    drift_score: float = 0.0
    significant: bool = False

    # Distribution comparison
    ref_mean: float = 0.0
    ref_std: float = 0.0
    ref_median: float = 0.0
    ref_skewness: float = 0.0
    ref_kurtosis: float = 0.0

    cur_mean: float = 0.0
    cur_std: float = 0.0
    cur_median: float = 0.0
    cur_skewness: float = 0.0
    cur_kurtosis: float = 0.0

    # Performance impact
    predicted_performance_degradation: float = 0.0  # estimated IC decay

    # Timestamps
    reference_period_start: Optional[datetime] = None
    reference_period_end: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    checked_at: datetime = field(default_factory=datetime.utcnow)

    def to_alert_dict(self) -> Dict[str, Any]:
        """Format for alerting systems."""
        return {
            "drift_score": self.drift_score,
            "significant": self.significant,
            "mean_shift": self.cur_mean - self.ref_mean,
            "std_change_ratio": self.cur_std / max(self.ref_std, 1e-8),
            "predicted_degradation": self.predicted_performance_degradation,
        }


class PredictionDriftDetector:
    """Detects distribution shifts in model predictions.

    Prediction drift is often the most actionable signal:
    - If predictions shift systematically, the model may be stale
    - If prediction variance changes, uncertainty has changed
    - If prediction distribution diverges, the market regime may have shifted
    """

    def __init__(self, threshold: float = 0.05) -> None:
        self.threshold = threshold
        self._history: List[PredictionDriftResult] = []

    # -- Detect --

    async def detect(
        self,
        reference_predictions: Any,
        current_predictions: Any,
        reference_timestamps: Optional[List[datetime]] = None,
        current_timestamps: Optional[List[datetime]] = None,
    ) -> PredictionDriftResult:
        """Detect prediction distribution drift.

        Args:
            reference_predictions: Predictions from training/evaluation period.
            current_predictions: Predictions from current production period.
            reference_timestamps: Optional timestamps for reference.
            current_timestamps: Optional timestamps for current.

        Returns:
            PredictionDriftResult.
        """
        result = PredictionDriftResult()

        # Placeholder: actual prediction drift computation
        # Compute PSI, KS, JS between reference and current predictions

        result.drift_score = 0.0
        result.significant = result.drift_score > self.threshold

        if reference_timestamps:
            result.reference_period_start = min(reference_timestamps) if reference_timestamps else None
            result.reference_period_end = max(reference_timestamps) if reference_timestamps else None
        if current_timestamps:
            result.current_period_start = min(current_timestamps) if current_timestamps else None
            result.current_period_end = max(current_timestamps) if current_timestamps else None

        self._history.append(result)

        logger.info("Prediction drift: score=%.4f, significant=%s, mean_shift=%.4f",
                     result.drift_score, result.significant, result.cur_mean - result.ref_mean)

        return result

    # -- Performance Impact Estimation --

    async def estimate_performance_impact(self, drift_result: PredictionDriftResult) -> float:
        """Estimate how much model performance may degrade due to drift.

        Based on empirical relationship between prediction drift
        and IC/Rank IC degradation.
        """
        return drift_result.drift_score * 2.0

    # -- History --

    def get_history(self, limit: int = 50) -> List[PredictionDriftResult]:
        """Get recent drift results."""
        return self._history[-limit:]

    def get_trend(self, window: int = 10) -> float:
        """Get drift trend (slope over recent window)."""
        recent = self._history[-window:]
        if len(recent) < 2:
            return 0.0
        # Linear trend approximation
        scores = [r.drift_score for r in recent]
        return (scores[-1] - scores[0]) / len(scores)

    def is_accelerating(self) -> bool:
        """Check if drift is accelerating (trend > 0)."""
        return self.get_trend(window=10) > 0.001
