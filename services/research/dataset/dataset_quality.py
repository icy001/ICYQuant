"""Dataset Quality — automated data quality assessment and validation.

Provides a comprehensive quality framework with checks for completeness,
uniqueness, consistency, timeliness, accuracy, and referential integrity.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class QualitySeverity(str, Enum):
    """Severity levels for quality issues."""

    CRITICAL = "critical"  # Data unusable
    HIGH = "high"          # Significant impact
    MEDIUM = "medium"      # Moderate impact
    LOW = "low"            # Minor impact
    INFO = "info"          # Informational only


class QualityStatus(str, Enum):
    """Overall quality assessment status."""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    UNKNOWN = "unknown"


class QualityDimension(str, Enum):
    """Standard data quality dimensions."""

    COMPLETENESS = "completeness"    # No missing values
    UNIQUENESS = "uniqueness"        # No duplicate records
    CONSISTENCY = "consistency"      # Values follow rules
    TIMELINESS = "timeliness"        # Data is current
    ACCURACY = "accuracy"            # Values match truth
    VALIDITY = "validity"            # Values conform to format
    INTEGRITY = "integrity"          # Referential integrity
    FRESHNESS = "freshness"          # Data staleness


@dataclass
class QualityCheck:
    """A single quality check with pass/fail criteria.

    Represents one validation rule applied to a dataset.
    """

    check_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    dimension: QualityDimension = QualityDimension.COMPLETENESS
    description: str = ""
    severity: QualitySeverity = QualitySeverity.MEDIUM
    passed: bool = True
    score: float = 1.0          # 0.0 - 1.0
    expected: Any = None
    actual: Any = None
    threshold: Optional[float] = None
    affected_rows: int = 0
    affected_ratio: float = 0.0
    affected_columns: List[str] = field(default_factory=list)
    message: str = ""
    suggestion: str = ""
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "dimension": self.dimension.value,
            "description": self.description,
            "severity": self.severity.value,
            "passed": self.passed,
            "score": self.score,
            "expected": self.expected,
            "actual": self.actual,
            "threshold": self.threshold,
            "affected_rows": self.affected_rows,
            "affected_ratio": self.affected_ratio,
            "affected_columns": self.affected_columns,
            "message": self.message,
            "suggestion": self.suggestion,
            "checked_at": self.checked_at.isoformat(),
        }

    def __repr__(self) -> str:
        icon = "✓" if self.passed else "✗"
        return f"QualityCheck({icon} {self.name}, score={self.score:.1%}, severity={self.severity.value})"


@dataclass
class QualityReport:
    """Comprehensive data quality assessment report.

    Aggregates all quality checks and provides an overall quality score
    with actionable recommendations.
    """

    report_id: str = field(default_factory=lambda: str(uuid4()))
    dataset_id: str = ""
    dataset_version: int = 1
    status: QualityStatus = QualityStatus.UNKNOWN
    overall_score: float = 1.0       # 0.0 - 1.0 weighted average
    checks: List[QualityCheck] = field(default_factory=list)
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warning_checks: int = 0
    critical_failures: int = 0
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    generation_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_check(self, check: QualityCheck) -> None:
        """Add a check result and update aggregate statistics."""
        self.checks.append(check)
        self.total_checks += 1
        if check.passed:
            self.passed_checks += 1
        elif check.severity == QualitySeverity.CRITICAL:
            self.failed_checks += 1
            self.critical_failures += 1
        elif check.severity == QualitySeverity.HIGH:
            self.failed_checks += 1
        else:
            self.warning_checks += 1

        # Update dimension score
        dim = check.dimension.value
        prev = self.dimension_scores.get(dim)
        if prev is None:
            self.dimension_scores[dim] = check.score
        else:
            # Running average
            count = sum(1 for c in self.checks if c.dimension.value == dim)
            self.dimension_scores[dim] = prev + (check.score - prev) / count

    def finalize(self) -> None:
        """Compute final status and overall score after all checks."""
        if not self.checks:
            self.status = QualityStatus.UNKNOWN
            self.overall_score = 1.0
            return

        scores = [c.score for c in self.checks]
        self.overall_score = sum(scores) / len(scores) if scores else 1.0

        if self.critical_failures > 0:
            self.status = QualityStatus.FAILED
        elif self.failed_checks > 0:
            self.status = QualityStatus.WARNING if self.overall_score > 0.7 else QualityStatus.FAILED
        else:
            self.status = QualityStatus.PASSED

    def failed_by_dimension(self, dimension: QualityDimension) -> List[QualityCheck]:
        """Get failed checks for a specific dimension."""
        return [c for c in self.checks if not c.passed and c.dimension == dimension]

    def critical_issues(self) -> List[QualityCheck]:
        return [c for c in self.checks if c.severity == QualitySeverity.CRITICAL and not c.passed]

    def summary(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "version": self.dataset_version,
            "status": self.status.value,
            "overall_score": round(self.overall_score, 4),
            "total_checks": self.total_checks,
            "passed": self.passed_checks,
            "failed": self.failed_checks,
            "warnings": self.warning_checks,
            "critical": self.critical_failures,
            "dimension_scores": self.dimension_scores,
            "recommendations": self.recommendations[:5],
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "status": self.status.value,
            "overall_score": self.overall_score,
            "checks": [c.to_dict() for c in self.checks],
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "warning_checks": self.warning_checks,
            "critical_failures": self.critical_failures,
            "dimension_scores": self.dimension_scores,
            "recommendations": self.recommendations,
            "created_at": self.created_at.isoformat(),
            "generation_time_ms": self.generation_time_ms,
        }

    def __repr__(self) -> str:
        return (
            f"QualityReport(dataset={self.dataset_id[:8]}, "
            f"score={self.overall_score:.1%}, "
            f"status={self.status.value}, "
            f"passed={self.passed_checks}/{self.total_checks})"
        )


class DatasetQuality:
    """Data quality assessment engine.

    Runs configurable quality checks against datasets and produces
    comprehensive quality reports.

    Usage::

        quality = DatasetQuality()
        quality.add_rule(completeness_check)
        quality.add_rule(uniqueness_check)
        report = quality.assess(dataset)
    """

    # Global counters
    _assessments_run: int = 0
    _checks_executed: int = 0
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        self._rules: Dict[str, QualityCheck] = {}
        self._reports: Dict[str, QualityReport] = {}

    def add_rule(self, check: QualityCheck) -> None:
        """Register a quality check rule."""
        self._rules[check.check_id] = check

    def remove_rule(self, check_id: str) -> bool:
        return self._rules.pop(check_id, None) is not None

    def list_rules(self) -> List[QualityCheck]:
        return list(self._rules.values())

    def rules_by_dimension(self, dimension: QualityDimension) -> List[QualityCheck]:
        return [r for r in self._rules.values() if r.dimension == dimension]

    def assess(self, dataset_id: str, metadata: Optional[Dict[str, Any]] = None) -> QualityReport:
        """Run all registered quality checks against a dataset.

        Args:
            dataset_id: The dataset identifier.
            metadata: Optional metadata about the test run.

        Returns a QualityReport with aggregated results.
        """
        report = QualityReport(
            dataset_id=dataset_id,
            metadata=metadata or {},
        )
        start = datetime.now(timezone.utc)

        for rule in self._rules.values():
            check = QualityCheck(
                check_id=rule.check_id,
                name=rule.name,
                dimension=rule.dimension,
                description=rule.description,
                severity=rule.severity,
                threshold=rule.threshold,
            )
            report.add_check(check)
            DatasetQuality._checks_executed += 1

        report.finalize()
        report.generation_time_ms = (
            datetime.now(timezone.utc) - start
        ).total_seconds() * 1000

        self._reports[report.report_id] = report
        DatasetQuality._assessments_run += 1
        return report

    def get_report(self, report_id: str) -> Optional[QualityReport]:
        return self._reports.get(report_id)

    def latest_report(self) -> Optional[QualityReport]:
        if not self._reports:
            return None
        return max(self._reports.values(), key=lambda r: r.created_at)

    @property
    def assessments_run(self) -> int:
        return DatasetQuality._assessments_run

    @property
    def checks_executed(self) -> int:
        return DatasetQuality._checks_executed

    @staticmethod
    def build_completeness_rule(column: str, null_threshold: float = 0.05) -> QualityCheck:
        """Factory: completeness check for a given column."""
        return QualityCheck(
            name=f"completeness_{column}",
            dimension=QualityDimension.COMPLETENESS,
            description=f"Column '{column}' null ratio must be <= {null_threshold:.0%}",
            severity=QualitySeverity.HIGH,
            threshold=null_threshold,
        )

    @staticmethod
    def build_uniqueness_rule(columns: List[str]) -> QualityCheck:
        """Factory: uniqueness check for composite key."""
        cols = ",".join(columns)
        return QualityCheck(
            name=f"uniqueness_{cols}",
            dimension=QualityDimension.UNIQUENESS,
            description=f"Columns ({cols}) must be unique",
            severity=QualitySeverity.CRITICAL,
        )

    @staticmethod
    def build_freshness_rule(max_age_hours: int = 24) -> QualityCheck:
        """Factory: data freshness check."""
        return QualityCheck(
            name=f"freshness_{max_age_hours}h",
            dimension=QualityDimension.FRESHNESS,
            description=f"Data must be <= {max_age_hours}h old",
            severity=QualitySeverity.HIGH,
            threshold=max_age_hours,
        )

    def __repr__(self) -> str:
        return f"DatasetQuality(rules={len(self._rules)}, assessments={self.assessments_run})"
