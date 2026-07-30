"""Feature Monitor — real-time feature drift and quality monitoring.

Monitors feature distributions for drift between training and
production, detects data quality degradation, and sends alerts.

Usage::

    from services.feature_store import FeatureMonitor, DriftReport

    monitor = FeatureMonitor()
    report = monitor.check_drift(
        "ema20", training_values, production_values
    )
    if report.status == DriftStatus.DRIFT_DETECTED:
        print("Alert: Feature drift!")
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class DriftStatus(str, Enum):
    """Drift detection result status."""

    STABLE = "stable"            # No drift detected
    WARNING = "warning"          # Minor drift, needs attention
    DRIFT_DETECTED = "drift_detected"  # Significant drift
    INSUFFICIENT_DATA = "insufficient_data"


class DriftMethod(str, Enum):
    """Supported drift detection methods."""

    PSI = "psi"              # Population Stability Index
    KS_TEST = "ks_test"      # Kolmogorov-Smirnov test
    MEAN_SHIFT = "mean_shift"  # Mean shift ratio
    STD_SHIFT = "std_shift"    # Standard deviation shift ratio


@dataclass
class DriftReport:
    """Result of a drift detection check.

    Attributes:
        feature_name: Feature being monitored.
        status: Overall drift status.
        psi_value: Population Stability Index value.
        ks_statistic: KS test statistic.
        ks_pvalue: KS test p-value.
        training_stats: Statistics from training distribution.
        production_stats: Statistics from production distribution.
        drift_details: Per-method drift results.
        checked_at: Unix timestamp.
    """

    feature_name: str
    status: DriftStatus = DriftStatus.STABLE
    psi_value: float = 0.0
    ks_statistic: float = 0.0
    ks_pvalue: float = 1.0
    training_stats: Dict[str, float] = field(default_factory=dict)
    production_stats: Dict[str, float] = field(default_factory=dict)
    drift_details: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    checked_at: float = field(default_factory=time.time)


@dataclass
class MonitoringConfig:
    """Configuration for feature monitoring.

    Attributes:
        psi_threshold: PSI value above which drift is considered detected.
        ks_pvalue_threshold: p-value below which KS test is significant.
        mean_shift_threshold: Relative mean shift ratio for alert.
        std_shift_threshold: Relative std shift ratio for alert.
        n_bins_psi: Number of bins for PSI calculation.
        min_samples: Minimum samples required for drift check.
    """

    psi_threshold: float = 0.25
    ks_pvalue_threshold: float = 0.05
    mean_shift_threshold: float = 0.1
    std_shift_threshold: float = 0.1
    n_bins_psi: int = 10
    min_samples: int = 30


class FeatureMonitor:
    """Real-time feature drift and quality monitor.

    Performs multiple statistical tests to detect distribution
    shifts between training and production data.
    """

    # ---- 分组：初始化 ----

    def __init__(self, config: Optional[MonitoringConfig] = None) -> None:
        """Initialize the monitor.

        Args:
            config: Monitoring configuration. Uses defaults if not provided.
        """
        self.config = config or MonitoringConfig()
        self._history: Dict[str, List[DriftReport]] = {}

    # ---- 分组：漂移检测 ----

    def check_drift(
        self,
        feature_name: str,
        training_values: List[float],
        production_values: List[float],
    ) -> DriftReport:
        """Check for feature drift between training and production distributions.

        Args:
            feature_name: Feature name.
            training_values: Values from training distribution.
            production_values: Values from production distribution.

        Returns:
            DriftReport with detailed analysis.
        """
        report = DriftReport(feature_name=feature_name)

        clean_train = [v for v in training_values if v is not None and not (isinstance(v, float) and v != v)]
        clean_prod = [v for v in production_values if v is not None and not (isinstance(v, float) and v != v)]

        if len(clean_train) < self.config.min_samples or len(clean_prod) < self.config.min_samples:
            report.status = DriftStatus.INSUFFICIENT_DATA
            return report

        # Compute statistics
        report.training_stats = self._compute_stats(clean_train)
        report.production_stats = self._compute_stats(clean_prod)

        # Run drift detection methods
        drift_results: Dict[str, Dict[str, Any]] = {}
        any_drift = False
        any_warning = False

        # PSI
        psi = self._compute_psi(clean_train, clean_prod)
        report.psi_value = psi
        if psi > self.config.psi_threshold:
            drift_results["psi"] = {"status": "drift", "value": psi, "threshold": self.config.psi_threshold}
            any_drift = True
        elif psi > self.config.psi_threshold * 0.5:
            drift_results["psi"] = {"status": "warning", "value": psi, "threshold": self.config.psi_threshold}
            any_warning = True
        else:
            drift_results["psi"] = {"status": "stable", "value": psi}

        # KS test
        ks_stat, ks_pval = self._compute_ks(clean_train, clean_prod)
        report.ks_statistic = ks_stat
        report.ks_pvalue = ks_pval
        if ks_pval < self.config.ks_pvalue_threshold:
            drift_results["ks_test"] = {
                "status": "drift",
                "statistic": ks_stat,
                "pvalue": ks_pval,
                "threshold": self.config.ks_pvalue_threshold,
            }
            any_drift = True
        else:
            drift_results["ks_test"] = {"status": "stable", "statistic": ks_stat, "pvalue": ks_pval}

        # Mean shift
        mean_train = report.training_stats.get("mean", 0)
        mean_prod = report.production_stats.get("mean", 0)
        if mean_train != 0:
            mean_shift = abs(mean_prod - mean_train) / abs(mean_train)
        else:
            mean_shift = abs(mean_prod - mean_train) if mean_prod != 0 else 0

        if mean_shift > self.config.mean_shift_threshold:
            drift_results["mean_shift"] = {"status": "drift", "shift_ratio": mean_shift}
            any_drift = True
        elif mean_shift > self.config.mean_shift_threshold * 0.5:
            drift_results["mean_shift"] = {"status": "warning", "shift_ratio": mean_shift}
            any_warning = True
        else:
            drift_results["mean_shift"] = {"status": "stable", "shift_ratio": mean_shift}

        # Std shift
        std_train = report.training_stats.get("std", 1)
        std_prod = report.production_stats.get("std", 1)
        if std_train != 0:
            std_shift = abs(std_prod - std_train) / abs(std_train)
        else:
            std_shift = 0

        if std_shift > self.config.std_shift_threshold:
            drift_results["std_shift"] = {"status": "drift", "shift_ratio": std_shift}
            any_drift = True
        elif std_shift > self.config.std_shift_threshold * 0.5:
            drift_results["std_shift"] = {"status": "warning", "shift_ratio": std_shift}
            any_warning = True
        else:
            drift_results["std_shift"] = {"status": "stable", "shift_ratio": std_shift}

        report.drift_details = drift_results

        if any_drift:
            report.status = DriftStatus.DRIFT_DETECTED
        elif any_warning:
            report.status = DriftStatus.WARNING
        else:
            report.status = DriftStatus.STABLE

        # Record history
        self._history.setdefault(feature_name, []).append(report)

        return report

    # ---- 分组：查询 ----

    def get_history(self, feature_name: str) -> List[DriftReport]:
        """Get drift check history for a feature.

        Args:
            feature_name: Feature name.

        Returns:
            List of DriftReport, newest first.
        """
        history = list(self._history.get(feature_name, []))
        history.sort(key=lambda r: r.checked_at, reverse=True)
        return history

    def get_latest_status(self, feature_name: str) -> Optional[DriftStatus]:
        """Get the latest drift status for a feature.

        Args:
            feature_name: Feature name.

        Returns:
            DriftStatus or None if no checks performed.
        """
        history = self._history.get(feature_name, [])
        if not history:
            return None
        return history[-1].status

    def list_drifted_features(self) -> List[str]:
        """List all features currently in drift or warning state.

        Returns:
            Sorted list of feature names.
        """
        drifted = []
        for name, history in self._history.items():
            if history and history[-1].status in (
                DriftStatus.DRIFT_DETECTED,
                DriftStatus.WARNING,
            ):
                drifted.append(name)
        drifted.sort()
        return drifted

    # ---- 分组：统计计算 ----

    @staticmethod
    def _compute_stats(values: List[float]) -> Dict[str, float]:
        """Compute basic statistics for a value list."""
        n = len(values)
        if n == 0:
            return {"count": 0, "mean": 0, "std": 0, "min": 0, "max": 0}

        mean_val = sum(values) / n
        variance = sum((v - mean_val) ** 2 for v in values) / n
        std_val = math.sqrt(variance)

        return {
            "count": n,
            "mean": mean_val,
            "std": std_val,
            "min": min(values),
            "max": max(values),
            "p25": sorted(values)[n // 4] if n >= 4 else min(values),
            "p50": sorted(values)[n // 2],
            "p75": sorted(values)[3 * n // 4] if n >= 4 else max(values),
        }

    def _compute_psi(
        self,
        training: List[float],
        production: List[float],
    ) -> float:
        """Compute Population Stability Index.

        PSI = sum((actual_i - expected_i) * ln(actual_i / expected_i))
        """
        n_bins = self.config.n_bins
        all_vals = training + production
        min_val, max_val = min(all_vals), max(all_vals)

        if min_val == max_val:
            return 0.0

        bin_width = (max_val - min_val) / n_bins
        epsilon = 1e-10

        psi = 0.0
        n_train = len(training)
        n_prod = len(production)

        for i in range(n_bins):
            bin_low = min_val + i * bin_width
            bin_high = bin_low + bin_width

            train_in_bin = sum(1 for v in training if bin_low <= v < bin_high or (i == n_bins - 1 and v == bin_high))
            prod_in_bin = sum(1 for v in production if bin_low <= v < bin_high or (i == n_bins - 1 and v == bin_high))

            expected = (train_in_bin / n_train) if n_train > 0 else epsilon
            actual = (prod_in_bin / n_prod) if n_prod > 0 else epsilon

            if actual > 0 and expected > 0:
                psi += (actual - expected) * math.log(actual / expected)

        return psi

    @staticmethod
    def _compute_ks(
        training: List[float],
        production: List[float],
    ) -> Tuple[float, float]:
        """Compute two-sample KS test statistic and approximate p-value.

        Returns:
            (ks_statistic, approximate_pvalue)
        """
        train_sorted = sorted(training)
        prod_sorted = sorted(production)

        n1, n2 = len(train_sorted), len(prod_sorted)
        i, j = 0, 0
        d_max = 0.0

        while i < n1 and j < n2:
            if train_sorted[i] < prod_sorted[j]:
                d = abs((i + 1) / n1 - j / n2)
                i += 1
            elif train_sorted[i] > prod_sorted[j]:
                d = abs(i / n1 - (j + 1) / n2)
                j += 1
            else:
                d = abs((i + 1) / n1 - (j + 1) / n2)
                i += 1
                j += 1
            d_max = max(d_max, d)

        while i < n1:
            d = abs((i + 1) / n1 - j / n2)
            d_max = max(d_max, d)
            i += 1
        while j < n2:
            d = abs(i / n1 - (j + 1) / n2)
            d_max = max(d_max, d)
            j += 1

        # Approximate p-value using the Kolmogorov distribution
        lambda_stat = d_max * math.sqrt(n1 * n2 / (n1 + n2))
        # Simplified approximation
        p_value = 2 * math.exp(-2 * lambda_stat ** 2) if lambda_stat > 0 else 1.0
        p_value = min(p_value, 1.0)

        return d_max, p_value
