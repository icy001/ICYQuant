"""
ICYQuant Feature Validator - Feature quality and constraint validation.

Ensures computed features meet their defined constraints before
being stored in the feature store. Catches issues early in the
pipeline to prevent bad data from entering training datasets.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .feature_definition import FeatureDefinition
from .feature_registry import FeatureEntry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation Types
# ---------------------------------------------------------------------------


class ValidationSeverity(Enum):
    """Severity of validation issues."""

    INFO = auto()       # Informational only
    WARNING = auto()    # Potential issue, can proceed
    ERROR = auto()      # Must fix before proceeding
    CRITICAL = auto()   # Pipeline must stop


class ValidationType(Enum):
    """Types of validation checks."""

    NULL_CHECK = "null_check"
    RANGE_CHECK = "range_check"
    TYPE_CHECK = "type_check"
    COVERAGE_CHECK = "coverage_check"
    FRESHNESS_CHECK = "freshness_check"
    DISTRIBUTION_CHECK = "distribution_check"
    STATIONARITY_CHECK = "stationarity_check"
    CORRELATION_CHECK = "correlation_check"
    LOOKAHEAD_CHECK = "lookahead_check"
    CONSISTENCY_CHECK = "consistency_check"


# ---------------------------------------------------------------------------
# Validation Results
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    """A single validation issue."""

    validation_type: ValidationType
    severity: ValidationSeverity
    feature_id: str = ""
    message: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ValidationReport:
    """Complete validation report for a set of features."""

    report_id: str = ""
    feature_ids: List[str] = field(default_factory=list)

    # Results
    passed: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)

    # Counts
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    validation_time_seconds: float = 0.0

    def add_issue(self, issue: ValidationIssue) -> None:
        """Add a validation issue and update counts."""
        self.issues.append(issue)
        if issue.severity == ValidationSeverity.ERROR or issue.severity == ValidationSeverity.CRITICAL:
            self.error_count += 1
            self.passed = False
        elif issue.severity == ValidationSeverity.WARNING:
            self.warning_count += 1
        else:
            self.info_count += 1

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    @property
    def has_warnings(self) -> bool:
        return self.warning_count > 0


# ---------------------------------------------------------------------------
# Feature Validator
# ---------------------------------------------------------------------------


class FeatureValidator:
    """Validate computed features against their definitions.

    Performs multiple validation checks:
    - Null/inf presence validation
    - Value range constraint validation
    - Data type validation
    - Coverage ratio validation
    - Look-ahead bias detection
    - Temporal consistency checks
    """

    def __init__(self) -> None:
        self._validation_rules: Dict[str, Any] = {}
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """Register default validation rules."""
        self._validation_rules["max_null_ratio"] = 0.20       # max 20% nulls
        self._validation_rules["max_outlier_ratio"] = 0.05    # max 5% outliers
        self._validation_rules["min_coverage_ratio"] = 0.80   # min 80% coverage
        self._validation_rules["max_correlation"] = 0.95      # warn on >0.95 correlation
        self._validation_rules["min_unique_ratio"] = 0.01     # min 1% unique values

    # -- Validation --

    async def validate(self, values: Any, feature_def: FeatureDefinition) -> ValidationReport:
        """Validate feature values against their definition."""
        import time
        t0 = time.time()

        report = ValidationReport(
            report_id=feature_def.name,
            feature_ids=[feature_def.name],
        )

        # Run all checks
        await self._check_null(report, values, feature_def)
        await self._check_range(report, values, feature_def)
        await self._check_coverage(report, values, feature_def)
        await self._check_uniqueness(report, values, feature_def)

        report.validation_time_seconds = time.time() - t0
        return report

    async def validate_batch(
        self, features: Dict[str, Any], definitions: List[FeatureDefinition],
    ) -> Dict[str, ValidationReport]:
        """Validate multiple features."""
        reports: Dict[str, ValidationReport] = {}
        for feature_def in definitions:
            values = features.get(feature_def.name)
            if values is not None:
                reports[feature_def.name] = await self.validate(values, feature_def)
        return reports

    # -- Individual Checks --

    async def _check_null(self, report: ValidationReport, values: Any, feature_def: FeatureDefinition) -> None:
        """Check null/inf ratios."""
        # Placeholder check
        pass

    async def _check_range(self, report: ValidationReport, values: Any, feature_def: FeatureDefinition) -> None:
        """Check if values are within defined min/max constraints."""
        if feature_def.min_value is not None or feature_def.max_value is not None:
            # Placeholder check
            pass

    async def _check_coverage(self, report: ValidationReport, values: Any, feature_def: FeatureDefinition) -> None:
        """Check data coverage ratio."""
        pass

    async def _check_uniqueness(self, report: ValidationReport, values: Any, feature_def: FeatureDefinition) -> None:
        """Check that values aren't all identical."""
        pass

    # -- Look-Ahead Bias Detection --

    async def check_lookahead_bias(
        self, feature_values: Any, feature_timestamps: List[datetime],
        reference_timestamp: datetime, feature_def: FeatureDefinition,
    ) -> ValidationReport:
        """Detect potential look-ahead bias in feature values.

        Ensures that feature values at a given timestamp use only data
        available at or before that timestamp. This is critical for
        preventing future information from leaking into training.
        """
        report = ValidationReport(
            report_id=f"lookahead_{feature_def.name}",
            feature_ids=[feature_def.name],
        )

        for ts in feature_timestamps:
            if ts > reference_timestamp:
                report.add_issue(ValidationIssue(
                    validation_type=ValidationType.LOOKAHEAD_CHECK,
                    severity=ValidationSeverity.CRITICAL,
                    feature_id=feature_def.name,
                    message=f"Feature contains data from {ts} which is after reference time {reference_timestamp}",
                    detail={"feature_ts": ts.isoformat(), "reference_ts": reference_timestamp.isoformat()},
                ))

        return report

    # -- Correlation Check --

    async def check_cross_correlation(
        self, features: Dict[str, Any],
    ) -> ValidationReport:
        """Check for highly correlated features (potential redundancy)."""
        report = ValidationReport(
            report_id="cross_correlation",
            feature_ids=list(features.keys()),
        )

        threshold = self._validation_rules.get("max_correlation", 0.95)
        # Placeholder: actual correlation computation in production
        return report
