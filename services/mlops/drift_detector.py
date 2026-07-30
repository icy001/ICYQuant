"""
Drift Detection Engine.

Detects two types of drift:
1. Data Drift — distribution shift between training and production data
2. Model Drift — degradation of prediction accuracy over time

Triggers retraining events when drift exceeds thresholds.
"""

import enum
import time
import uuid
import math
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DriftSeverity(str, enum.Enum):
    """Severity of detected drift."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DriftMethod(str, enum.Enum):
    """Statistical methods for drift detection."""
    PSI = "psi"                      # Population Stability Index
    KS_TEST = "ks_test"              # Kolmogorov-Smirnov test
    WASSERSTEIN = "wasserstein"      # Wasserstein distance
    JENSEN_SHANNON = "jensen_shannon"  # Jensen-Shannon divergence
    MEAN_SHIFT = "mean_shift"        # Simple mean comparison
    STD_SHIFT = "std_shift"          # Standard deviation comparison
    PREDICTION_ERROR = "prediction_error"  # Model prediction accuracy


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DriftConfig:
    """Configuration for drift detection."""

    # Data drift
    data_drift_method: DriftMethod = DriftMethod.PSI
    data_drift_threshold_psi: float = 0.2
    data_drift_window_size: int = 1000  # samples for comparison
    data_drift_check_interval_hours: float = 24.0

    # Model drift
    model_drift_method: DriftMethod = DriftMethod.PREDICTION_ERROR
    model_drift_window_days: int = 30
    model_drift_min_samples: int = 100
    prediction_error_increase_pct: float = 0.3  # 30% error increase = drift

    # Statistical test thresholds
    ks_test_alpha: float = 0.01
    wasserstein_threshold: float = 0.3

    # Severity thresholds
    psi_low: float = 0.1
    psi_medium: float = 0.2
    psi_high: float = 0.5

    # Actions
    auto_trigger_retrain: bool = True
    auto_trigger_rollback: bool = False
    alert_on_drift: bool = True

    # Reference data
    reference_data_ttl_days: int = 90  # How long to keep training reference


@dataclass
class DataDriftResult:
    """Result of data drift detection for a single feature or model."""

    feature_name: str = ""
    method: DriftMethod = DriftMethod.PSI
    drift_detected: bool = False
    severity: DriftSeverity = DriftSeverity.NONE

    # Metrics
    psi_value: float = 0.0
    ks_statistic: float = 0.0
    ks_pvalue: float = 1.0
    wasserstein_distance: float = 0.0

    # Distribution statistics
    reference_mean: float = 0.0
    reference_std: float = 0.0
    current_mean: float = 0.0
    current_std: float = 0.0
    mean_shift: float = 0.0

    # Sample sizes
    reference_count: int = 0
    current_count: int = 0

    checked_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "method": self.method.value,
            "drift_detected": self.drift_detected,
            "severity": self.severity.value,
            "psi_value": self.psi_value,
            "ks_statistic": self.ks_statistic,
            "ks_pvalue": self.ks_pvalue,
            "reference_mean": self.reference_mean,
            "current_mean": self.current_mean,
            "mean_shift": self.mean_shift,
            "reference_count": self.reference_count,
            "current_count": self.current_count,
            "checked_at": self.checked_at,
        }


@dataclass
class ModelDriftResult:
    """Result of model drift detection."""

    model_name: str = ""
    drift_detected: bool = False
    severity: DriftSeverity = DriftSeverity.NONE

    # Prediction accuracy
    baseline_accuracy: float = 0.0
    current_accuracy: float = 0.0
    accuracy_change_pct: float = 0.0

    # Error metrics
    baseline_rmse: float = 0.0
    current_rmse: float = 0.0
    rmse_change_pct: float = 0.0

    # Prediction distribution
    baseline_pred_mean: float = 0.0
    current_pred_mean: float = 0.0
    pred_mean_shift: float = 0.0

    # PSI of predictions
    prediction_psi: float = 0.0

    # Sample counts
    baseline_count: int = 0
    current_count: int = 0

    checked_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "drift_detected": self.drift_detected,
            "severity": self.severity.value,
            "baseline_accuracy": self.baseline_accuracy,
            "current_accuracy": self.current_accuracy,
            "accuracy_change_pct": self.accuracy_change_pct,
            "baseline_rmse": self.baseline_rmse,
            "current_rmse": self.current_rmse,
            "rmse_change_pct": self.rmse_change_pct,
            "prediction_psi": self.prediction_psi,
            "checked_at": self.checked_at,
        }


@dataclass
class DriftReport:
    """Comprehensive drift report for a model."""

    report_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    model_name: str = ""
    generated_at: float = field(default_factory=time.time)

    # Data drift per feature
    feature_drifts: List[DataDriftResult] = field(default_factory=list)
    any_data_drift: bool = False
    data_drift_severity: DriftSeverity = DriftSeverity.NONE

    # Model drift
    model_drift: Optional[ModelDriftResult] = None
    any_model_drift: bool = False
    model_drift_severity: DriftSeverity = DriftSeverity.NONE

    # Overall
    requires_retraining: bool = False
    requires_rollback: bool = False
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "model_name": self.model_name,
            "generated_at": self.generated_at,
            "any_data_drift": self.any_data_drift,
            "data_drift_severity": self.data_drift_severity.value,
            "any_model_drift": self.any_model_drift,
            "model_drift_severity": self.model_drift_severity.value,
            "feature_drifts": [d.to_dict() for d in self.feature_drifts],
            "model_drift": self.model_drift.to_dict() if self.model_drift else None,
            "requires_retraining": self.requires_retraining,
            "requires_rollback": self.requires_rollback,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Drift Detector
# ---------------------------------------------------------------------------

class DriftDetector:
    """Detects data and model drift in production ML systems.

    Compares current production data/predictions against training
    baselines to detect distribution shifts and performance degradation.

    Usage::

        detector = DriftDetector(config)
        detector.set_reference("NVDA", training_features)
        report = detector.check_drift("Alpha_v38")
        if report.requires_retraining:
            # trigger retraining
    """

    def __init__(self, config: DriftConfig):
        self.config = config
        self._reference_data: Dict[str, Dict[str, List[float]]] = {}
        self._reference_predictions: Dict[str, Dict[str, float]] = {}
        self._history: List[DriftReport] = []
        self._on_drift_callbacks: List[Callable] = []

    # ------------------------------------------------------------------
    # Reference Data Management
    # ------------------------------------------------------------------

    def set_reference(
        self,
        model_name: str,
        features: Dict[str, List[float]],
        predictions: Optional[List[float]] = None,
        actuals: Optional[List[float]] = None,
    ) -> None:
        """Set the training reference data for a model.

        Args:
            model_name: Model identifier.
            features: Feature name → list of training values.
            predictions: Optional training predictions.
            actuals: Optional training actuals (for accuracy baseline).
        """
        self._reference_data[model_name] = {
            k: list(v) for k, v in features.items()
        }

        if predictions and actuals:
            self._reference_predictions[model_name] = {
                "predictions": list(predictions),
                "actuals": list(actuals),
                "accuracy": self._compute_accuracy(predictions, actuals),
                "rmse": self._compute_rmse(predictions, actuals),
                "pred_mean": self._mean(predictions),
                "pred_std": self._std(predictions),
            }

        logger.info(
            f"Reference data set for {model_name}: "
            f"{len(features)} features, {len(next(iter(features.values()), []))} samples"
        )

    def clear_reference(self, model_name: str) -> None:
        """Clear reference data for a model."""
        self._reference_data.pop(model_name, None)
        self._reference_predictions.pop(model_name, None)

    # ------------------------------------------------------------------
    # Drift Detection
    # ------------------------------------------------------------------

    def check_data_drift(
        self,
        model_name: str,
        current_features: Dict[str, List[float]],
        method: Optional[DriftMethod] = None,
    ) -> List[DataDriftResult]:
        """Check for data drift across all features.

        Args:
            model_name: Model to check.
            current_features: Current production feature values.
            method: Drift detection method (default from config).

        Returns:
            List of per-feature DataDriftResult.
        """
        method = method or self.config.data_drift_method
        reference = self._reference_data.get(model_name, {})

        if not reference:
            logger.warning(f"No reference data for {model_name}")
            return []

        results: List[DataDriftResult] = []
        for feature_name, ref_values in reference.items():
            cur_values = current_features.get(feature_name, [])
            if not cur_values:
                continue

            result = self._detect_feature_drift(
                feature_name, ref_values, cur_values, method
            )
            results.append(result)

            if result.drift_detected:
                logger.info(
                    f"Data drift detected: {feature_name} "
                    f"PSI={result.psi_value:.3f}, severity={result.severity.value}"
                )

        return results

    def check_model_drift(
        self,
        model_name: str,
        current_predictions: List[float],
        current_actuals: Optional[List[float]] = None,
    ) -> Optional[ModelDriftResult]:
        """Check for model prediction drift.

        Args:
            model_name: Model to check.
            current_predictions: Recent production predictions.
            current_actuals: Optional actual outcomes (for accuracy).

        Returns:
            ModelDriftResult or None if no reference.
        """
        ref = self._reference_predictions.get(model_name)
        if not ref:
            logger.warning(f"No reference predictions for {model_name}")
            return None

        result = ModelDriftResult(
            model_name=model_name,
            baseline_accuracy=ref.get("accuracy", 0),
            baseline_rmse=ref.get("rmse", 0),
            baseline_pred_mean=ref.get("pred_mean", 0),
            current_count=len(current_predictions),
            baseline_count=len(ref.get("predictions", [])),
        )

        # Prediction distribution shift (PSI)
        result.prediction_psi = self._compute_psi(
            ref.get("predictions", []), current_predictions, bins=10
        )

        # Prediction mean shift
        result.current_pred_mean = self._mean(current_predictions)
        if abs(result.baseline_pred_mean) > 1e-9:
            result.pred_mean_shift = abs(
                result.current_pred_mean - result.baseline_pred_mean
            ) / abs(result.baseline_pred_mean)

        # Accuracy degradation
        if current_actuals:
            result.current_accuracy = self._compute_accuracy(current_predictions, current_actuals)
            result.current_rmse = self._compute_rmse(current_predictions, current_actuals)

            if result.baseline_accuracy > 0:
                result.accuracy_change_pct = (
                    result.baseline_accuracy - result.current_accuracy
                ) / result.baseline_accuracy

            if result.baseline_rmse > 0:
                result.rmse_change_pct = (
                    result.current_rmse - result.baseline_rmse
                ) / result.baseline_rmse

        # Determine if drift detected
        result.drift_detected = (
            result.prediction_psi > self.config.data_drift_threshold_psi
            or result.accuracy_change_pct > self.config.prediction_error_increase_pct
            or result.rmse_change_pct > self.config.prediction_error_increase_pct
        )

        result.severity = self._classify_severity(result.prediction_psi)

        if result.drift_detected:
            logger.warning(
                f"Model drift detected: {model_name} "
                f"PSI={result.prediction_psi:.3f}, "
                f"accuracy_change={result.accuracy_change_pct:.1%}, "
                f"severity={result.severity.value}"
            )

        return result

    def check_drift(
        self,
        model_name: str,
        current_features: Dict[str, List[float]],
        current_predictions: Optional[List[float]] = None,
        current_actuals: Optional[List[float]] = None,
    ) -> DriftReport:
        """Full drift check: data + model.

        Returns:
            Comprehensive DriftReport.
        """
        report = DriftReport(model_name=model_name)

        # Data drift
        report.feature_drifts = self.check_data_drift(model_name, current_features)
        report.any_data_drift = any(d.drift_detected for d in report.feature_drifts)

        if report.any_data_drift:
            severities = [d.severity for d in report.feature_drifts if d.drift_detected]
            report.data_drift_severity = max(
                severities,
                key=lambda s: ["none", "low", "medium", "high", "critical"].index(s.value),
            )

        # Model drift
        if current_predictions:
            report.model_drift = self.check_model_drift(
                model_name, current_predictions, current_actuals
            )
            report.any_model_drift = (
                report.model_drift.drift_detected if report.model_drift else False
            )
            report.model_drift_severity = (
                report.model_drift.severity if report.model_drift else DriftSeverity.NONE
            )

        # Actions
        report.requires_retraining = (
            report.any_data_drift
            or report.any_model_drift
            or (
                report.data_drift_severity
                in (DriftSeverity.MEDIUM, DriftSeverity.HIGH, DriftSeverity.CRITICAL)
            )
        )

        report.requires_rollback = (
            report.model_drift_severity in (DriftSeverity.HIGH, DriftSeverity.CRITICAL)
            and self.config.auto_trigger_rollback
        )

        # Summary
        parts = []
        if report.any_data_drift:
            drifted = [d.feature_name for d in report.feature_drifts if d.drift_detected]
            parts.append(f"Data drift ({report.data_drift_severity.value}) in: {drifted}")
        if report.any_model_drift:
            parts.append(f"Model drift ({report.model_drift_severity.value})")
        if not parts:
            parts.append("No drift detected")

        report.summary = "; ".join(parts)

        self._history.append(report)

        if report.requires_retraining or report.requires_rollback:
            self._notify_drift(report)

        return report

    # ------------------------------------------------------------------
    # Statistical Methods
    # ------------------------------------------------------------------

    def _detect_feature_drift(
        self,
        feature_name: str,
        reference: List[float],
        current: List[float],
        method: DriftMethod,
    ) -> DataDriftResult:
        """Detect drift for a single feature."""
        result = DataDriftResult(
            feature_name=feature_name,
            method=method,
            reference_mean=self._mean(reference),
            reference_std=self._std(reference),
            current_mean=self._mean(current),
            current_std=self._std(current),
            reference_count=len(reference),
            current_count=len(current),
        )

        result.mean_shift = abs(result.current_mean - result.reference_mean)

        if method == DriftMethod.PSI:
            result.psi_value = self._compute_psi(reference, current)
            result.drift_detected = result.psi_value > self.config.data_drift_threshold_psi
            result.severity = self._classify_severity(result.psi_value)

        elif method == DriftMethod.KS_TEST:
            ks_stat, ks_pval = self._ks_test(reference, current)
            result.ks_statistic = ks_stat
            result.ks_pvalue = ks_pval
            result.drift_detected = ks_pval < self.config.ks_test_alpha
            result.severity = DriftSeverity.HIGH if result.drift_detected else DriftSeverity.NONE

        elif method == DriftMethod.WASSERSTEIN:
            result.wasserstein_distance = self._wasserstein(reference, current)
            result.drift_detected = result.wasserstein_distance > self.config.wasserstein_threshold
            result.severity = self._classify_severity(result.wasserstein_distance)

        elif method == DriftMethod.MEAN_SHIFT:
            if abs(result.reference_mean) > 1e-9:
                relative_shift = result.mean_shift / abs(result.reference_mean)
                result.psi_value = relative_shift  # reuse psi field for convenience
                result.drift_detected = relative_shift > self.config.data_drift_threshold_psi
                result.severity = self._classify_severity(relative_shift)

        return result

    @staticmethod
    def _compute_psi(
        expected: List[float],
        actual: List[float],
        bins: int = 10,
    ) -> float:
        """Compute Population Stability Index."""
        if not expected or not actual:
            return 0.0

        all_vals = expected + actual
        min_val, max_val = min(all_vals), max(all_vals)

        if abs(max_val - min_val) < 1e-9:
            return 0.0

        bin_edges = [min_val + i * (max_val - min_val) / bins for i in range(bins + 1)]

        def _bin_counts(data: List[float]) -> List[float]:
            counts = [0.0] * bins
            for v in data:
                for i in range(bins):
                    if bin_edges[i] <= v < bin_edges[i + 1]:
                        counts[i] += 1
                        break
                else:
                    counts[-1] += 1  # last bin includes max
            total = len(data)
            return [c / total if total > 0 else 0 for c in counts]

        expected_dist = _bin_counts(expected)
        actual_dist = _bin_counts(actual)

        psi = 0.0
        epsilon = 1e-10
        for e, a in zip(expected_dist, actual_dist):
            e = max(e, epsilon)
            a = max(a, epsilon)
            psi += (a - e) * math.log(a / e)

        return psi

    @staticmethod
    def _ks_test(
        data1: List[float], data2: List[float]
    ) -> Tuple[float, float]:
        """Approximate two-sample Kolmogorov-Smirnov test.

        Returns (D_statistic, p_value).
        """
        if not data1 or not data2:
            return 0.0, 1.0

        sorted1 = sorted(data1)
        sorted2 = sorted(data2)
        n1, n2 = len(sorted1), len(sorted2)

        # Compute empirical CDFs
        d_max = 0.0
        i, j = 0, 0
        while i < n1 and j < n2:
            d = abs((i + 1) / n1 - (j + 1) / n2)
            d_max = max(d_max, d)

            if sorted1[i] < sorted2[j]:
                i += 1
            elif sorted1[i] > sorted2[j]:
                j += 1
            else:
                i += 1
                j += 1

        # Approximate p-value
        en = math.sqrt(n1 * n2 / (n1 + n2))
        lambda_stat = (en + 0.12 + 0.11 / en) * d_max

        # Kolmogorov approximation
        p_value = 2.0 * sum(
            (-1) ** (k - 1) * math.exp(-2 * k * k * lambda_stat * lambda_stat)
            for k in range(1, 100)
        )
        p_value = min(1.0, max(0.0, p_value))

        return d_max, p_value

    @staticmethod
    def _wasserstein(data1: List[float], data2: List[float]) -> float:
        """Compute 1D Wasserstein (Earth Mover's) distance."""
        if not data1 or not data2:
            return 0.0
        sorted1 = sorted(data1)
        sorted2 = sorted(data2)

        # If lengths differ, interpolate the shorter one
        n = min(len(sorted1), len(sorted2))
        if len(sorted1) != len(sorted2):
            # Use the shorter length for approximation
            step1 = len(sorted1) / n
            step2 = len(sorted2) / n
            s1 = [sorted1[int(i * step1)] for i in range(n)]
            s2 = [sorted2[int(i * step2)] for i in range(n)]
        else:
            s1, s2 = sorted1, sorted2

        return sum(abs(a - b) for a, b in zip(s1, s2)) / n

    @staticmethod
    def _compute_accuracy(predictions: List[float], actuals: List[float]) -> float:
        """Compute directional accuracy (for trading models)."""
        if len(predictions) < 2 or len(actuals) < 2:
            return 0.0
        correct = sum(
            1 for p, a in zip(predictions, actuals)
            if (p > 0 and a > 0) or (p < 0 and a < 0) or (p == 0 and a == 0)
        )
        return correct / len(predictions)

    @staticmethod
    def _compute_rmse(predictions: List[float], actuals: List[float]) -> float:
        """Compute Root Mean Squared Error."""
        if not predictions or not actuals:
            return 0.0
        n = min(len(predictions), len(actuals))
        mse = sum((predictions[i] - actuals[i]) ** 2 for i in range(n)) / n
        return math.sqrt(mse)

    @staticmethod
    def _mean(data: List[float]) -> float:
        if not data:
            return 0.0
        return sum(data) / len(data)

    @staticmethod
    def _std(data: List[float]) -> float:
        if len(data) < 2:
            return 0.0
        m = sum(data) / len(data)
        return math.sqrt(sum((x - m) ** 2 for x in data) / (len(data) - 1))

    def _classify_severity(self, value: float) -> DriftSeverity:
        """Classify a metric value into a severity level."""
        if value < self.config.psi_low:
            return DriftSeverity.NONE
        elif value < self.config.psi_medium:
            return DriftSeverity.LOW
        elif value < self.config.psi_high:
            return DriftSeverity.MEDIUM
        else:
            return DriftSeverity.HIGH

    # ------------------------------------------------------------------
    # Callbacks & History
    # ------------------------------------------------------------------

    def on_drift(self, callback: Callable) -> None:
        """Register a callback for drift events."""
        self._on_drift_callbacks.append(callback)

    def _notify_drift(self, report: DriftReport) -> None:
        for cb in self._on_drift_callbacks:
            try:
                cb(report)
            except Exception as e:
                logger.error(f"Drift callback error: {e}")

    def get_history(
        self, model_name: Optional[str] = None, limit: int = 50
    ) -> List[DriftReport]:
        """Get drift detection history."""
        reports = self._history
        if model_name:
            reports = [r for r in reports if r.model_name == model_name]
        return sorted(reports, key=lambda r: r.generated_at, reverse=True)[:limit]

    def get_latest_report(self, model_name: str) -> Optional[DriftReport]:
        """Get the most recent drift report for a model."""
        for r in sorted(self._history, key=lambda x: x.generated_at, reverse=True):
            if r.model_name == model_name:
                return r
        return None

    def reset(self) -> None:
        """Reset detector state (for testing)."""
        self._reference_data.clear()
        self._reference_predictions.clear()
        self._history.clear()
