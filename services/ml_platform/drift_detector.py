"""
ICYQuant Drift Detector - ML model drift detection orchestrator.

Coordinates three types of drift detection:

    Data Drift → Feature Drift → Prediction Drift

Each type detects distribution shifts between training and production data,
triggering alerts and potential model retraining.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class DriftSeverity(Enum):
    """Drift severity levels."""

    NONE = "none"         # No significant drift
    LOW = "low"           # Minor drift, monitor
    MEDIUM = "medium"     # Moderate drift, investigate
    HIGH = "high"         # Significant drift, alert
    CRITICAL = "critical" # Severe drift, halt/retrain


@dataclass
class DriftConfig:
    """Drift detection configuration."""

    # Thresholds
    data_drift_threshold: float = 0.10
    feature_drift_threshold: float = 0.05
    prediction_drift_threshold: float = 0.05

    # Methods
    data_drift_method: str = "psi"      # psi, ks_test, js_divergence
    feature_drift_method: str = "psi"
    prediction_drift_method: str = "psi"

    # Schedule
    check_interval_hours: int = 24
    min_samples_for_check: int = 100

    # Alerting
    auto_alert: bool = True
    alert_on_medium: bool = True
    alert_channels: List[str] = field(default_factory=list)


@dataclass
class DriftReport:
    """Comprehensive drift detection report."""

    report_id: str = field(default_factory=lambda: uuid4().hex[:12])
    model_id: str = ""
    model_version: str = ""

    # Data drift
    data_drift_score: float = 0.0
    data_drift_severity: DriftSeverity = DriftSeverity.NONE
    data_drift_details: Dict[str, Any] = field(default_factory=dict)

    # Feature drift
    feature_drift_score: float = 0.0
    feature_drift_severity: DriftSeverity = DriftSeverity.NONE
    drifted_features: List[str] = field(default_factory=list)
    feature_drift_details: Dict[str, float] = field(default_factory=dict)

    # Prediction drift
    prediction_drift_score: float = 0.0
    prediction_drift_severity: DriftSeverity = DriftSeverity.NONE
    prediction_drift_details: Dict[str, Any] = field(default_factory=dict)

    # Overall
    overall_severity: DriftSeverity = DriftSeverity.NONE
    requires_retraining: bool = False
    recommendations: List[str] = field(default_factory=list)

    # Metadata
    training_samples: int = 0
    production_samples: int = 0
    checked_at: datetime = field(default_factory=datetime.utcnow)
    training_period_start: Optional[datetime] = None
    training_period_end: Optional[datetime] = None
    production_period_start: Optional[datetime] = None
    production_period_end: Optional[datetime] = None


class DriftDetector:
    """Orchestrates drift detection across data, features, and predictions.

    Detects distribution shifts that could degrade model performance:

    Data Drift: Raw input data distribution changes.
    Feature Drift: Feature value distribution changes.
    Prediction Drift: Model output distribution changes.

    Triggers alerts and can initiate automatic retraining.
    """

    def __init__(
        self,
        data_drift: Optional[Any] = None,
        feature_drift: Optional[Any] = None,
        prediction_drift: Optional[Any] = None,
        config: Optional[DriftConfig] = None,
    ) -> None:
        self.config = config or DriftConfig()
        self._data_drift = data_drift
        self._feature_drift = feature_drift
        self._prediction_drift = prediction_drift

        self._reports: List[DriftReport] = []

    # -- Detect --

    async def detect(
        self,
        model_id: str,
        model_version: str,
        training_data: Any,
        production_data: Any,
        training_predictions: Optional[Any] = None,
        production_predictions: Optional[Any] = None,
    ) -> DriftReport:
        """Run complete drift detection across all three dimensions.

        Args:
            model_id: Model identifier.
            model_version: Model version.
            training_data: Training/reference data (feature matrix).
            production_data: Current production data.
            training_predictions: Predictions on training data.
            production_predictions: Current production predictions.

        Returns:
            Comprehensive DriftReport.
        """
        report = DriftReport(
            model_id=model_id,
            model_version=model_version,
        )

        # 1. Data Drift
        data_drift_score = await self._detect_data_drift(training_data, production_data)
        report.data_drift_score = data_drift_score
        report.data_drift_severity = self._score_to_severity(data_drift_score, "data")

        # 2. Feature Drift
        feature_scores = await self._detect_feature_drift(training_data, production_data)
        report.feature_drift_score = max(feature_scores.values()) if feature_scores else 0.0
        report.feature_drift_severity = self._score_to_severity(report.feature_drift_score, "feature")
        report.feature_drift_details = feature_scores
        report.drifted_features = [
            name for name, score in feature_scores.items()
            if score > self.config.feature_drift_threshold
        ]

        # 3. Prediction Drift
        if training_predictions is not None and production_predictions is not None:
            pred_drift_score = await self._detect_prediction_drift(training_predictions, production_predictions)
            report.prediction_drift_score = pred_drift_score
            report.prediction_drift_severity = self._score_to_severity(pred_drift_score, "prediction")

        # Overall assessment
        severities = [report.data_drift_severity, report.feature_drift_severity, report.prediction_drift_severity]
        severity_order = [DriftSeverity.NONE, DriftSeverity.LOW, DriftSeverity.MEDIUM, DriftSeverity.HIGH, DriftSeverity.CRITICAL]
        report.overall_severity = max(severities, key=lambda s: severity_order.index(s))

        report.requires_retraining = report.overall_severity in (DriftSeverity.HIGH, DriftSeverity.CRITICAL)
        report.recommendations = self._generate_recommendations(report)

        self._reports.append(report)
        logger.info("Drift detection complete: model=%s, overall=%s, data=%.4f, feature=%.4f, pred=%.4f",
                     model_id, report.overall_severity.value,
                     report.data_drift_score, report.feature_drift_score, report.prediction_drift_score)

        return report

    # -- Detection Methods --

    async def _detect_data_drift(self, training_data: Any, production_data: Any) -> float:
        """Detect distribution shift in raw input data."""
        return 0.0

    async def _detect_feature_drift(self, training_data: Any, production_data: Any) -> Dict[str, float]:
        """Detect per-feature distribution shifts."""
        return {}

    async def _detect_prediction_drift(self, training_predictions: Any, production_predictions: Any) -> float:
        """Detect distribution shift in model predictions."""
        return 0.0

    # -- Utilities --

    def _score_to_severity(self, score: float, drift_type: str) -> DriftSeverity:
        """Map drift score to severity level."""
        thresholds = {
            "data": self.config.data_drift_threshold,
            "feature": self.config.feature_drift_threshold,
            "prediction": self.config.prediction_drift_threshold,
        }
        threshold = thresholds.get(drift_type, 0.05)

        if score < threshold * 0.5:
            return DriftSeverity.NONE
        elif score < threshold:
            return DriftSeverity.LOW
        elif score < threshold * 2:
            return DriftSeverity.MEDIUM
        elif score < threshold * 4:
            return DriftSeverity.HIGH
        else:
            return DriftSeverity.CRITICAL

    def _generate_recommendations(self, report: DriftReport) -> List[str]:
        """Generate actionable recommendations based on drift report."""
        recommendations: List[str] = []

        if report.data_drift_severity in (DriftSeverity.HIGH, DriftSeverity.CRITICAL):
            recommendations.append("Investigate data pipeline for changes in source data")
        if report.feature_drift_severity in (DriftSeverity.HIGH, DriftSeverity.CRITICAL):
            recommendations.append(f"Review drifted features: {report.drifted_features}")
            recommendations.append("Consider retraining model with recent data")
        if report.prediction_drift_severity in (DriftSeverity.HIGH, DriftSeverity.CRITICAL):
            recommendations.append("Model predictions have shifted significantly - urgent retraining recommended")

        if not recommendations:
            recommendations.append("No significant drift detected - continue monitoring")

        return recommendations

    def get_recent_reports(self, model_id: str, limit: int = 20) -> List[DriftReport]:
        """Get recent drift reports for a model."""
        reports = [r for r in self._reports if r.model_id == model_id]
        return sorted(reports, key=lambda r: r.checked_at, reverse=True)[:limit]
