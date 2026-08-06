"""Feature Validator — validate feature data quality and consistency.

Ensures features meet quality standards before entering the factor pipeline:
* Missing value checks
* Distribution checks
* Coverage checks
* Staleness checks
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FeatureValidationReport:
    """Report from a feature validation run."""

    feature_name: str
    passed: bool = True
    checks: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            self.passed = False

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        self.passed = False

    def summary(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "passed": self.passed,
            "checks_passed": sum(1 for c in self.checks if c["passed"]),
            "checks_failed": sum(1 for c in self.checks if not c["passed"]),
            "warnings": len(self.warnings),
            "errors": len(self.errors),
        }


class FeatureValidator:
    """Validates feature data quality and consistency.

    Checks:
    * Missing value ratio
    * Value range validity
    * Coverage ratio (non-null / total)
    * Distribution shape (skew, kurtosis bounds)
    * Staleness (last update recency)
    """

    def __init__(self) -> None:
        self._max_missing_ratio: float = 0.3
        self._min_coverage: float = 0.7
        self._max_skew: float = 5.0
        self._max_kurtosis: float = 20.0

    def validate(
        self,
        feature_name: str,
        values: List[Optional[float]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FeatureValidationReport:
        """Validate a feature's data quality."""
        report = FeatureValidationReport(feature_name=feature_name)

        if not values:
            report.add_error("Empty feature values")
            return report

        n = len(values)
        non_null = [v for v in values if v is not None]
        n_non_null = len(non_null)

        # Missing value check
        missing_ratio = 1.0 - (n_non_null / n)
        report.add_check(
            "missing_ratio",
            missing_ratio <= self._max_missing_ratio,
            f"missing_ratio={missing_ratio:.4f} (threshold={self._max_missing_ratio})",
        )
        if missing_ratio > self._max_missing_ratio:
            report.add_error(f"Missing ratio {missing_ratio:.4f} exceeds {self._max_missing_ratio}")

        # Coverage check
        coverage = n_non_null / n if n > 0 else 0
        report.add_check(
            "coverage",
            coverage >= self._min_coverage,
            f"coverage={coverage:.4f} (threshold={self._min_coverage})",
        )

        # Value range check
        if non_null:
            min_val = min(non_null)
            max_val = max(non_null)
            if min_val == max_val:
                report.add_warning("All non-null values are identical")

            # Finite check
            all_finite = all(
                v is not None and v == v and v != float("inf") and v != float("-inf")
                for v in values
            )
            report.add_check(
                "finite_values",
                all_finite,
                "All values are finite",
            )

            # Distribution checks
            mean = sum(non_null) / n_non_null
            variance = sum((v - mean) ** 2 for v in non_null) / n_non_null
            if variance > 0:
                std = variance ** 0.5
                skew = sum(((v - mean) / std) ** 3 for v in non_null) / n_non_null
                kurt = sum(((v - mean) / std) ** 4 for v in non_null) / n_non_null - 3

                report.add_check(
                    "skewness",
                    abs(skew) <= self._max_skew,
                    f"skew={skew:.4f} (threshold={self._max_skew})",
                )
                report.add_check(
                    "kurtosis",
                    abs(kurt) <= self._max_kurtosis,
                    f"kurtosis={kurt:.4f} (threshold={self._max_kurtosis})",
                )

        # Staleness check (if metadata includes last_update)
        if metadata and "last_updated" in metadata:
            try:
                last_updated = datetime.fromisoformat(metadata["last_updated"])
                staleness_days = (datetime.now(timezone.utc) - last_updated).days
                report.add_check(
                    "staleness",
                    staleness_days <= 7,
                    f"staleness={staleness_days}d (threshold=7d)",
                )
            except (ValueError, TypeError):
                report.add_warning("Could not parse last_updated timestamp")

        logger.info(
            "Feature %s validation: %s (checks: %d passed/%d failed)",
            feature_name,
            "PASSED" if report.passed else "FAILED",
            sum(1 for c in report.checks if c["passed"]),
            sum(1 for c in report.checks if not c["passed"]),
        )
        return report

    def validate_batch(
        self,
        features: Dict[str, List[Optional[float]]],
    ) -> Dict[str, FeatureValidationReport]:
        """Validate multiple features at once."""
        reports: Dict[str, FeatureValidationReport] = {}
        for name, values in features.items():
            reports[name] = self.validate(name, values)
        return reports
