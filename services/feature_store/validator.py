"""Feature Validator — data quality and integrity checks.

Automatically validates features for common issues:
missing values, duplicates, outliers, type errors, temporal
continuity, and look-ahead bias.

Usage::

    from services.feature_store import FeatureValidator, ValidationRule

    validator = FeatureValidator()
    report = validator.validate("ema20", values, timestamps)
    if not report.passed:
        print(report.errors)
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ValidationRule(str, Enum):
    """Supported validation rules."""

    MISSING_VALUES = "missing_values"
    DUPLICATE_INDEX = "duplicate_index"
    TYPE_CHECK = "type_check"
    OUTLIER_DETECTION = "outlier_detection"
    TEMPORAL_CONTINUITY = "temporal_continuity"
    LOOKAHEAD_BIAS = "lookahead_bias"
    VALUE_RANGE = "value_range"
    STATIONARITY = "stationarity"
    CUSTOM = "custom"


class Severity(str, Enum):
    """Validation issue severity."""

    ERROR = "error"    # Must fix — data is invalid
    WARNING = "warning"  # Should review — potentially problematic
    INFO = "info"      # Informational only


@dataclass
class ValidationIssue:
    """A single validation issue.

    Attributes:
        rule: The rule that caught this issue.
        severity: Issue severity.
        message: Human-readable description.
        details: Additional context (e.g. count, values).
    """

    rule: ValidationRule
    severity: Severity = Severity.ERROR
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Result of a feature validation run.

    Attributes:
        feature_name: Validated feature name.
        version: Feature version.
        passed: True if no ERROR-level issues found.
        issues: All issues found.
        summary: Key statistics about the validation.
        validated_at: Unix timestamp.
    """

    feature_name: str
    version: str = "v1"
    passed: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    validated_at: float = field(default_factory=time.time)

    @property
    def errors(self) -> List[ValidationIssue]:
        """Get ERROR-level issues only."""
        return [i for i in self.issues if i.severity == Severity.ERROR]

    @property
    def warnings(self) -> List[ValidationIssue]:
        """Get WARNING-level issues only."""
        return [i for i in self.issues if i.severity == Severity.WARNING]

    @property
    def info(self) -> List[ValidationIssue]:
        """Get INFO-level issues only."""
        return [i for i in self.issues if i.severity == Severity.INFO]

    def add_issue(self, issue: ValidationIssue) -> None:
        """Add an issue and update pass/fail status."""
        self.issues.append(issue)
        if issue.severity == Severity.ERROR:
            self.passed = False


class FeatureValidator:
    """Validates feature data quality and integrity.

    Performs a configurable set of checks against feature data,
    returning a detailed ValidationReport.
    """

    # ---- 分组：初始化 ----

    def __init__(
        self,
        outlier_std_threshold: float = 5.0,
        max_missing_ratio: float = 0.05,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        enabled_rules: Optional[List[ValidationRule]] = None,
    ) -> None:
        """Initialize the validator with thresholds.

        Args:
            outlier_std_threshold: Number of standard deviations for outlier detection.
            max_missing_ratio: Maximum allowed ratio of missing values (0.0-1.0).
            min_value: Optional global minimum value bound.
            max_value: Optional global maximum value bound.
            enabled_rules: Which rules to run (default: all except CUSTOM).
        """
        self.outlier_std_threshold = outlier_std_threshold
        self.max_missing_ratio = max_missing_ratio
        self.min_value = min_value
        self.max_value = max_value
        self.enabled_rules = enabled_rules or [
            ValidationRule.MISSING_VALUES,
            ValidationRule.DUPLICATE_INDEX,
            ValidationRule.TYPE_CHECK,
            ValidationRule.OUTLIER_DETECTION,
            ValidationRule.VALUE_RANGE,
            ValidationRule.LOOKAHEAD_BIAS,
        ]

    # ---- 分组：校验 ----

    def validate(
        self,
        feature_name: str,
        values: List[float],
        timestamps: Optional[List[float]] = None,
        version: str = "v1",
        expected_dtype: type = float,
        reference_timestamps: Optional[List[float]] = None,
    ) -> ValidationReport:
        """Run all enabled validation rules.

        Args:
            feature_name: Feature name for the report.
            values: Feature values to validate.
            timestamps: Optional timestamps for temporal checks.
            version: Feature version.
            expected_dtype: Expected Python type for values.
            reference_timestamps: Reference timestamps for lookahead bias check.

        Returns:
            ValidationReport with all issues found.
        """
        report = ValidationReport(feature_name=feature_name, version=version)

        if ValidationRule.MISSING_VALUES in self.enabled_rules:
            self._check_missing(report, values)

        if ValidationRule.TYPE_CHECK in self.enabled_rules:
            self._check_type(report, values, expected_dtype)

        if ValidationRule.OUTLIER_DETECTION in self.enabled_rules:
            self._check_outliers(report, values)

        if ValidationRule.VALUE_RANGE in self.enabled_rules:
            self._check_range(report, values)

        if timestamps is not None:
            if ValidationRule.DUPLICATE_INDEX in self.enabled_rules:
                self._check_duplicates(report, timestamps)

            if ValidationRule.TEMPORAL_CONTINUITY in self.enabled_rules:
                self._check_temporal(report, timestamps)

            if (
                ValidationRule.LOOKAHEAD_BIAS in self.enabled_rules
                and reference_timestamps is not None
            ):
                self._check_lookahead(report, values, timestamps, reference_timestamps)

        report.summary = {
            "total_values": len(values),
            "issue_count": len(report.issues),
            "error_count": len(report.errors),
            "warning_count": len(report.warnings),
            "info_count": len(report.info),
        }

        return report

    # ---- 分组：单项检查 ----

    def _check_missing(self, report: ValidationReport, values: List[float]) -> None:
        """Check for missing (None / NaN) values."""
        if not values:
            report.add_issue(ValidationIssue(
                rule=ValidationRule.MISSING_VALUES,
                severity=Severity.ERROR,
                message="Feature has no values.",
                details={"count": 0},
            ))
            return

        missing_count = sum(1 for v in values if v is None or (isinstance(v, float) and v != v))
        missing_ratio = missing_count / len(values) if values else 0

        if missing_ratio > self.max_missing_ratio:
            report.add_issue(ValidationIssue(
                rule=ValidationRule.MISSING_VALUES,
                severity=Severity.ERROR,
                message=f"Missing ratio {missing_ratio:.2%} exceeds threshold {self.max_missing_ratio:.2%}.",
                details={"missing_count": missing_count, "total": len(values), "ratio": missing_ratio},
            ))
        elif missing_count > 0:
            report.add_issue(ValidationIssue(
                rule=ValidationRule.MISSING_VALUES,
                severity=Severity.WARNING,
                message=f"{missing_count} missing values found ({missing_ratio:.2%}).",
                details={"missing_count": missing_count, "total": len(values), "ratio": missing_ratio},
            ))

    def _check_type(self, report: ValidationReport, values: List[Any], expected_dtype: type) -> None:
        """Check that all values match the expected type."""
        type_errors = []
        for i, v in enumerate(values):
            if v is not None and not isinstance(v, expected_dtype):
                type_errors.append({"index": i, "value": v, "actual_type": type(v).__name__})

        if type_errors:
            report.add_issue(ValidationIssue(
                rule=ValidationRule.TYPE_CHECK,
                severity=Severity.ERROR,
                message=f"{len(type_errors)} values have wrong type (expected {expected_dtype.__name__}).",
                details={"errors": type_errors[:10], "count": len(type_errors)},
            ))

    def _check_outliers(self, report: ValidationReport, values: List[float]) -> None:
        """Detect statistical outliers using z-score."""
        clean = [v for v in values if v is not None and isinstance(v, (int, float)) and not (isinstance(v, float) and v != v)]
        if len(clean) < 3:
            return

        mean_val = statistics.mean(clean)
        std_val = statistics.stdev(clean)

        if std_val == 0:
            return

        outliers = [
            {"index": i, "value": v, "z_score": (v - mean_val) / std_val}
            for i, v in enumerate(values)
            if v is not None
            and abs((v - mean_val) / std_val) > self.outlier_std_threshold
        ]

        if outliers:
            report.add_issue(ValidationIssue(
                rule=ValidationRule.OUTLIER_DETECTION,
                severity=Severity.WARNING,
                message=f"{len(outliers)} outliers detected (>{self.outlier_std_threshold} std).",
                details={"outliers": outliers[:10], "count": len(outliers), "mean": mean_val, "std": std_val},
            ))

    def _check_range(self, report: ValidationReport, values: List[float]) -> None:
        """Check that values are within specified range."""
        if self.min_value is None and self.max_value is None:
            return

        out_of_range = []
        for i, v in enumerate(values):
            if v is None or not isinstance(v, (int, float)):
                continue
            if self.min_value is not None and v < self.min_value:
                out_of_range.append({"index": i, "value": v, "bound": "min", "threshold": self.min_value})
            elif self.max_value is not None and v > self.max_value:
                out_of_range.append({"index": i, "value": v, "bound": "max", "threshold": self.max_value})

        if out_of_range:
            report.add_issue(ValidationIssue(
                rule=ValidationRule.VALUE_RANGE,
                severity=Severity.ERROR,
                message=f"{len(out_of_range)} values outside allowed range.",
                details={"violations": out_of_range[:10], "count": len(out_of_range)},
            ))

    def _check_duplicates(self, report: ValidationReport, timestamps: List[float]) -> None:
        """Check for duplicate timestamps."""
        seen: Dict[float, int] = {}
        for t in timestamps:
            seen[t] = seen.get(t, 0) + 1

        duplicates = {t: c for t, c in seen.items() if c > 1}
        if duplicates:
            report.add_issue(ValidationIssue(
                rule=ValidationRule.DUPLICATE_INDEX,
                severity=Severity.ERROR,
                message=f"{len(duplicates)} duplicate timestamps found.",
                details={"duplicates": {str(k): v for k, v in list(duplicates.items())[:10]}, "count": len(duplicates)},
            ))

    def _check_temporal(self, report: ValidationReport, timestamps: List[float]) -> None:
        """Check temporal continuity (sorted, no gaps)."""
        if len(timestamps) < 2:
            return

        sorted_ts = sorted(timestamps)
        if sorted_ts != timestamps:
            report.add_issue(ValidationIssue(
                rule=ValidationRule.TEMPORAL_CONTINUITY,
                severity=Severity.WARNING,
                message="Timestamps are not monotonically increasing.",
                details={"first_unsorted_index": next(i for i in range(len(timestamps)) if timestamps[i] != sorted_ts[i])},
            ))

    def _check_lookahead(
        self,
        report: ValidationReport,
        values: List[float],
        timestamps: List[float],
        reference_timestamps: List[float],
    ) -> None:
        """Check for look-ahead bias by ensuring feature timestamps don't exceed reference."""
        if not timestamps or not reference_timestamps:
            return

        max_ref = max(reference_timestamps)
        violations = [
            {"index": i, "timestamp": ts}
            for i, ts in enumerate(timestamps)
            if ts > max_ref
        ]

        if violations:
            report.add_issue(ValidationIssue(
                rule=ValidationRule.LOOKAHEAD_BIAS,
                severity=Severity.ERROR,
                message=f"{len(violations)} timestamps exceed reference max — possible look-ahead bias.",
                details={"violations": violations[:10], "count": len(violations), "max_reference": max_ref},
            ))
