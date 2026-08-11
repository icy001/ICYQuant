"""
ICYQuant Drift Monitor — Online drift monitoring for deployed models.

Continuously monitors for:
  - Data drift (input distribution shifts)
  - Feature drift (individual feature shifts)
  - Prediction drift (output distribution shifts)
  - Concept drift (relationship between features and labels)

Provides real-time drift scores and automatic alerting
to trigger retraining workflows.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data
# ---------------------------------------------------------------------------

class DriftLevel(str, Enum):
    """Drift severity levels."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DriftScore:
    """Drift measurement for a single metric."""
    metric: str
    score: float
    level: DriftLevel
    threshold: float
    reference_value: float
    current_value: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DriftReport:
    """Comprehensive drift analysis report."""
    model_id: str
    timestamp: str
    data_drift: Dict[str, DriftScore] = field(default_factory=dict)
    feature_drift: Dict[str, DriftScore] = field(default_factory=dict)
    prediction_drift: Optional[DriftScore] = None
    overall_level: DriftLevel = DriftLevel.NONE
    recommendation: str = ""


# ---------------------------------------------------------------------------
# Drift Calculator
# ---------------------------------------------------------------------------

class DriftCalculator:
    """Statistical drift calculation utilities."""

    @staticmethod
    def psi(
        reference: np.ndarray,
        current: np.ndarray,
        bins: int = 10,
    ) -> float:
        """Calculate Population Stability Index (PSI).

        PSI < 0.1: no drift
        PSI 0.1 - 0.25: moderate drift
        PSI > 0.25: significant drift
        """
        if len(reference) == 0 or len(current) == 0:
            return 0.0

        # Determine bin edges from reference
        combined = np.concatenate([reference, current])
        min_val = np.min(combined)
        max_val = np.max(combined)

        if max_val <= min_val:
            return 0.0

        edges = np.linspace(min_val, max_val, bins + 1)
        # Extend edges slightly to capture all values
        edges[0] = -np.inf
        edges[-1] = np.inf

        ref_counts, _ = np.histogram(reference, bins=edges)
        cur_counts, _ = np.histogram(current, bins=edges)

        # Normalize (add small epsilon to avoid division by zero)
        epsilon = 1e-10
        ref_pct = (ref_counts / max(len(reference), 1)) + epsilon
        cur_pct = (cur_counts / max(len(current), 1)) + epsilon

        # PSI = sum((actual - expected) * ln(actual / expected))
        psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))

        return max(0.0, psi)

    @staticmethod
    def ks_statistic(reference: np.ndarray, current: np.ndarray) -> float:
        """Kolmogorov-Smirnov test statistic."""
        from scipy import stats
        if len(reference) == 0 or len(current) == 0:
            return 0.0
        try:
            ks, _ = stats.ks_2samp(reference, current)
            return float(ks)
        except Exception:
            return 0.0

    @staticmethod
    def wasserstein_distance(reference: np.ndarray, current: np.ndarray) -> float:
        """1D Wasserstein (Earth Mover's) distance."""
        if len(reference) == 0 or len(current) == 0:
            return 0.0
        ref_sorted = np.sort(reference)
        cur_sorted = np.sort(current)
        # Normalize by std of reference
        ref_std = max(np.std(reference), 1e-10)
        all_len = max(len(reference), len(current))
        distance = np.mean(np.abs(np.interp(
            np.linspace(0, 1, all_len),
            np.linspace(0, 1, len(ref_sorted)),
            ref_sorted,
        ) - np.interp(
            np.linspace(0, 1, all_len),
            np.linspace(0, 1, len(cur_sorted)),
            cur_sorted,
        )))
        return float(distance / ref_std)

    @staticmethod
    def mean_shift(reference: np.ndarray, current: np.ndarray) -> float:
        """Normalized mean shift."""
        if len(reference) == 0 or len(current) == 0:
            return 0.0
        ref_std = max(np.std(reference), 1e-10)
        return float(abs(np.mean(current) - np.mean(reference)) / ref_std)


# ---------------------------------------------------------------------------
# Drift Monitor
# ---------------------------------------------------------------------------

class DriftMonitor:
    """Online drift monitoring for deployed models.

    Usage::

        monitor = DriftMonitor()
        monitor.set_reference("nvda_model", features_ref, predictions_ref)

        # During inference
        monitor.record_features("nvda_model", live_features)
        monitor.record_prediction("nvda_model", live_prediction)
        report = monitor.check_drift("nvda_model")
    """

    def __init__(
        self,
        window_size: int = 1000,
        psi_threshold: float = 0.2,
        ks_threshold: float = 0.3,
        mean_shift_threshold: float = 1.0,
    ):
        self.window_size = window_size
        self.psi_threshold = psi_threshold
        self.ks_threshold = ks_threshold
        self.mean_shift_threshold = mean_shift_threshold
        self._initialized = False
        self._calculator = DriftCalculator()

        # Reference datasets: model_id → reference distribution
        self._reference_features: Dict[str, Dict[str, np.ndarray]] = {}
        self._reference_predictions: Dict[str, np.ndarray] = {}

        # Live windows
        self._live_features: Dict[str, Dict[str, Deque[float]]] = {}
        self._live_predictions: Dict[str, Deque[float]] = {}

        # Drift history
        self._drift_history: Dict[str, List[DriftReport]] = {}

        # Alert callbacks
        self._alert_callbacks: List[Callable[[DriftReport], None]] = []

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("DriftMonitor initialized")

    # ------------------------------------------------------------------
    # Reference data
    # ------------------------------------------------------------------

    def set_reference(
        self,
        model_id: str,
        features: Dict[str, np.ndarray],
        predictions: Optional[np.ndarray] = None,
    ) -> None:
        """Set reference distributions for drift comparison.

        Typically set from training data or a known-good deployment snapshot.

        Args:
            model_id: Model identifier.
            features: Reference feature distributions keyed by feature name.
            predictions: Reference prediction distribution.
        """
        self._reference_features[model_id] = {
            name: np.array(values)
            for name, values in features.items()
        }
        if predictions is not None:
            self._reference_predictions[model_id] = np.array(predictions)

        logger.info(
            "Reference set for %s: %d features, %d predictions",
            model_id, len(features),
            len(predictions) if predictions is not None else 0,
        )

    # ------------------------------------------------------------------
    # Recording live data
    # ------------------------------------------------------------------

    def record_features(
        self,
        model_id: str,
        features: Dict[str, float],
    ) -> None:
        """Record live feature values.

        Args:
            model_id: Model identifier.
            features: Feature values keyed by feature name.
        """
        if model_id not in self._live_features:
            self._live_features[model_id] = {}

        for name, value in features.items():
            if name not in self._live_features[model_id]:
                self._live_features[model_id][name] = deque(maxlen=self.window_size)
            self._live_features[model_id][name].append(value)

    def record_prediction(self, model_id: str, prediction: float) -> None:
        """Record a live prediction value."""
        if model_id not in self._live_predictions:
            self._live_predictions[model_id] = deque(maxlen=self.window_size)
        self._live_predictions[model_id].append(prediction)

    # ------------------------------------------------------------------
    # Drift detection
    # ------------------------------------------------------------------

    def check_drift(self, model_id: str) -> DriftReport:
        """Check for drift against reference distributions.

        Args:
            model_id: Model identifier.

        Returns:
            DriftReport with feature-level and prediction-level drift scores.
        """
        report = DriftReport(
            model_id=model_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Feature drift
        if model_id in self._reference_features and model_id in self._live_features:
            for feat_name, ref_arr in self._reference_features[model_id].items():
                live_data = self._live_features[model_id].get(feat_name)
                if live_data is None or len(live_data) < 50:
                    continue

                live_arr = np.array(live_data)
                psi = self._calculator.psi(ref_arr, live_arr)
                mean_shift = self._calculator.mean_shift(ref_arr, live_arr)

                # Aggregate score
                score = max(psi / self.psi_threshold,
                          mean_shift / self.mean_shift_threshold)
                level = self._score_to_level(score)

                report.feature_drift[feat_name] = DriftScore(
                    metric="feature_drift",
                    score=round(float(score), 4),
                    level=level,
                    threshold=1.0,
                    reference_value=round(float(np.mean(ref_arr)), 6),
                    current_value=round(float(np.mean(live_arr)), 6),
                )

        # Prediction drift
        if model_id in self._reference_predictions and model_id in self._live_predictions:
            ref_pred = self._reference_predictions[model_id]
            live_pred = np.array(self._live_predictions[model_id])

            if len(live_pred) >= 50:
                psi = self._calculator.psi(ref_pred, live_pred)
                ks = self._calculator.ks_statistic(ref_pred, live_pred)
                score = max(psi / self.psi_threshold, ks / self.ks_threshold)

                report.prediction_drift = DriftScore(
                    metric="prediction_drift",
                    score=round(float(score), 4),
                    level=self._score_to_level(score),
                    threshold=1.0,
                    reference_value=round(float(np.mean(ref_pred)), 6),
                    current_value=round(float(np.mean(live_pred)), 6),
                )

        # Determine overall level
        all_levels = [s.level for s in report.feature_drift.values()]
        if report.prediction_drift:
            all_levels.append(report.prediction_drift.level)

        severity = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        if all_levels:
            report.overall_level = max(all_levels, key=lambda x: severity[x])

        # Generate recommendation
        report.recommendation = self._generate_recommendation(report)

        # Record history
        if model_id not in self._drift_history:
            self._drift_history[model_id] = []
        self._drift_history[model_id].append(report)
        if len(self._drift_history[model_id]) > 100:
            self._drift_history[model_id] = self._drift_history[model_id][-100:]

        # Alert if significant
        if report.overall_level in (DriftLevel.HIGH, DriftLevel.CRITICAL):
            for cb in self._alert_callbacks:
                try:
                    cb(report)
                except Exception:
                    logger.exception("Drift alert callback error")

        return report

    def check_all(self) -> Dict[str, DriftReport]:
        """Check drift for all monitored models."""
        model_ids = set(
            list(self._reference_features.keys()) +
            list(self._live_features.keys())
        )
        return {mid: self.check_drift(mid) for mid in model_ids}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _score_to_level(self, score: float) -> DriftLevel:
        """Map drift score to severity level."""
        if score < 0.3:
            return DriftLevel.NONE
        if score < 0.7:
            return DriftLevel.LOW
        if score < 1.0:
            return DriftLevel.MEDIUM
        if score < 2.0:
            return DriftLevel.HIGH
        return DriftLevel.CRITICAL

    def _generate_recommendation(self, report: DriftReport) -> str:
        """Generate actionable recommendation based on drift report."""
        if report.overall_level in (DriftLevel.NONE, DriftLevel.LOW):
            return "No action needed — drift within normal bounds"

        if report.overall_level == DriftLevel.MEDIUM:
            return "Monitor closely — consider preparing retraining pipeline"

        if report.overall_level == DriftLevel.HIGH:
            return "Retrain model — significant distribution shift detected"

        return "URGENT: Retrain immediately — critical drift detected"

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_drift_history(self, model_id: str) -> List[Dict[str, Any]]:
        """Get historical drift reports."""
        history = self._drift_history.get(model_id, [])
        return [
            {
                "timestamp": r.timestamp,
                "overall_level": r.overall_level.value,
                "feature_drift_count": len(r.feature_drift),
                "prediction_drift_score": (
                    r.prediction_drift.score if r.prediction_drift else None
                ),
                "recommendation": r.recommendation,
            }
            for r in history[-20:]
        ]

    def on_alert(self, callback: Callable[[DriftReport], None]) -> None:
        self._alert_callbacks.append(callback)

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "models_monitored": len(self._reference_features),
            "drift_history_count": sum(len(h) for h in self._drift_history.values()),
        }

    def __repr__(self) -> str:
        return f"DriftMonitor(models={len(self._reference_features)})"
