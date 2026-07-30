"""Pipeline Validator.

Pipeline-level data validation ensuring data quality before
features are published to the feature store.

Usage::

    from services.feature_engineering import PipelineValidator

    validator = PipelineValidator()
    report = validator.validate(features, expected_columns=["ema20", "return"])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import numpy as np


class PipelineValidationRule(str, Enum):
    """Validation rules for pipeline output."""

    NO_MISSING_COLUMNS = "no_missing_columns"
    NO_ALL_NAN = "no_all_nan"
    NO_ALL_ZERO = "no_all_zero"
    NO_CONSTANT = "no_constant"
    ROW_COUNT_CONSISTENCY = "row_count_consistency"
    VALUE_RANGE = "value_range"
    NO_NEGATIVE_PRICES = "no_negative_prices"
    MIN_SAMPLE_COUNT = "min_sample_count"


@dataclass
class PipelineValidationReport:
    """Report of pipeline validation results.

    Attributes:
        is_valid: Overall validation result.
        rule_results: Per-rule pass/fail results.
        warnings: Non-fatal warnings.
        errors: Fatal validation errors.
        metadata: Additional diagnostic information.
    """

    is_valid: bool = True
    rule_results: Dict[str, bool] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        passed = sum(1 for v in self.rule_results.values() if v)
        total = len(self.rule_results)
        return f"PipelineValidationReport(passed={passed}/{total}, valid={self.is_valid})"


class PipelineValidator:
    """Validate pipeline output data quality.

    Runs a series of configurable checks on the output features
    before they are published to the feature store.

    Example::

        validator = PipelineValidator(
            rules=[
                PipelineValidationRule.NO_MISSING_COLUMNS,
                PipelineValidationRule.NO_ALL_NAN,
                PipelineValidationRule.ROW_COUNT_CONSISTENCY,
            ],
            expected_columns=["ema20", "momentum", "volatility"],
            min_rows=100,
        )
        report = validator.validate(features)
        if report.is_valid:
            print("Pipeline output is valid")
    """

    def __init__(
        self,
        rules: Optional[List[PipelineValidationRule]] = None,
        expected_columns: Optional[List[str]] = None,
        min_rows: int = 10,
        max_rows: Optional[int] = None,
        value_range: Optional[tuple[float, float]] = None,
    ) -> None:
        self.rules = rules or [
            PipelineValidationRule.NO_MISSING_COLUMNS,
            PipelineValidationRule.NO_ALL_NAN,
            PipelineValidationRule.NO_ALL_ZERO,
            PipelineValidationRule.ROW_COUNT_CONSISTENCY,
            PipelineValidationRule.MIN_SAMPLE_COUNT,
        ]
        self.expected_columns = expected_columns or []
        self.min_rows = min_rows
        self.max_rows = max_rows
        self.value_range = value_range

    def validate(self, features: Dict[str, List[float]]) -> PipelineValidationReport:
        """Validate pipeline output features.

        Args:
            features: Dict of feature_name -> list of values.

        Returns:
            PipelineValidationReport with pass/fail per rule.
        """
        report = PipelineValidationReport()
        rule_results: Dict[str, bool] = {}

        for rule in self.rules:
            passed = True
            try:
                if rule == PipelineValidationRule.NO_MISSING_COLUMNS:
                    passed = self._check_no_missing_columns(features, report)
                elif rule == PipelineValidationRule.NO_ALL_NAN:
                    passed = self._check_no_all_nan(features, report)
                elif rule == PipelineValidationRule.NO_ALL_ZERO:
                    passed = self._check_no_all_zero(features, report)
                elif rule == PipelineValidationRule.NO_CONSTANT:
                    passed = self._check_no_constant(features, report)
                elif rule == PipelineValidationRule.ROW_COUNT_CONSISTENCY:
                    passed = self._check_row_count_consistency(features, report)
                elif rule == PipelineValidationRule.VALUE_RANGE:
                    passed = self._check_value_range(features, report)
                elif rule == PipelineValidationRule.NO_NEGATIVE_PRICES:
                    passed = self._check_no_negative_prices(features, report)
                elif rule == PipelineValidationRule.MIN_SAMPLE_COUNT:
                    passed = self._check_min_sample_count(features, report)
            except Exception as e:
                passed = False
                report.errors.append(f"Rule '{rule.value}' raised: {e}")

            rule_results[rule.value] = passed
            if not passed:
                report.is_valid = False

        report.rule_results = rule_results
        report.metadata["feature_count"] = len(features)
        if features:
            lengths = [len(v) for v in features.values()]
            report.metadata["row_counts"] = {"min": min(lengths), "max": max(lengths), "median": int(np.median(lengths))}

        return report

    # ---- Rule implementations ----

    def _check_no_missing_columns(
        self, features: Dict[str, List[float]], report: PipelineValidationReport
    ) -> bool:
        """Verify all expected columns are present."""
        if not self.expected_columns:
            return True
        missing = [c for c in self.expected_columns if c not in features]
        if missing:
            report.errors.append(f"Missing expected columns: {missing}")
            return False
        return True

    def _check_no_all_nan(
        self, features: Dict[str, List[float]], report: PipelineValidationReport
    ) -> bool:
        """Verify no feature column is entirely NaN."""
        all_nan_cols: List[str] = []
        for name, values in features.items():
            arr = np.array(values, dtype=np.float64)
            if np.all(np.isnan(arr)):
                all_nan_cols.append(name)
        if all_nan_cols:
            report.errors.append(f"All-NaN columns: {all_nan_cols}")
            return False
        return True

    def _check_no_all_zero(
        self, features: Dict[str, List[float]], report: PipelineValidationReport
    ) -> bool:
        """Verify no feature column is entirely zero (excluding NaN)."""
        all_zero_cols: List[str] = []
        for name, values in features.items():
            arr = np.array(values, dtype=np.float64)
            valid = arr[~np.isnan(arr)]
            if len(valid) > 0 and np.all(valid == 0):
                all_zero_cols.append(name)
        if all_zero_cols:
            report.warnings.append(f"All-zero columns: {all_zero_cols}")
        return True  # warning only, not a hard failure

    def _check_no_constant(
        self, features: Dict[str, List[float]], report: PipelineValidationReport
    ) -> bool:
        """Warn if any feature column is constant (no variance)."""
        constant_cols: List[str] = []
        for name, values in features.items():
            arr = np.array(values, dtype=np.float64)
            valid = arr[~np.isnan(arr)]
            if len(valid) > 1 and np.nanstd(valid) == 0:
                constant_cols.append(name)
        if constant_cols:
            report.warnings.append(f"Constant columns (no variance): {constant_cols}")
        return True  # warning only

    def _check_row_count_consistency(
        self, features: Dict[str, List[float]], report: PipelineValidationReport
    ) -> bool:
        """Verify all feature columns have the same row count."""
        if not features:
            return True
        lengths = {name: len(values) for name, values in features.items()}
        if len(set(lengths.values())) > 1:
            report.errors.append(f"Inconsistent row counts: {lengths}")
            return False
        return True

    def _check_value_range(
        self, features: Dict[str, List[float]], report: PipelineValidationReport
    ) -> bool:
        """Verify values are within expected range."""
        if self.value_range is None:
            return True
        lo, hi = self.value_range
        for name, values in features.items():
            arr = np.array(values, dtype=np.float64)
            valid = arr[~np.isnan(arr)]
            if len(valid) == 0:
                continue
            if valid.min() < lo or valid.max() > hi:
                report.warnings.append(
                    f"Feature '{name}' outside expected range [{lo}, {hi}]: "
                    f"min={valid.min():.2f}, max={valid.max():.2f}"
                )
        return True  # warning only

    def _check_no_negative_prices(
        self, features: Dict[str, List[float]], report: PipelineValidationReport
    ) -> bool:
        """Verify price-like features are non-negative."""
        price_like = {"close", "price", "open", "high", "low", "vwap"}
        negative_cols: List[str] = []
        for name, values in features.items():
            if name.lower() not in price_like:
                continue
            arr = np.array(values, dtype=np.float64)
            valid = arr[~np.isnan(arr)]
            if len(valid) > 0 and np.any(valid < 0):
                negative_cols.append(name)
        if negative_cols:
            report.errors.append(f"Negative values in price columns: {negative_cols}")
            return False
        return True

    def _check_min_sample_count(
        self, features: Dict[str, List[float]], report: PipelineValidationReport
    ) -> bool:
        """Verify minimum row count is met."""
        if not features:
            report.errors.append(f"No features; minimum {self.min_rows} rows required")
            return False
        lengths = [len(v) for v in features.values()]
        min_len = min(lengths)
        if min_len < self.min_rows:
            report.errors.append(
                f"Insufficient rows: {min_len} < {self.min_rows} minimum"
            )
            return False
        if self.max_rows and max(lengths) > self.max_rows:
            report.warnings.append(
                f"Row count {max(lengths)} exceeds maximum {self.max_rows}"
            )
        return True
