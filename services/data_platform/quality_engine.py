"""ICYQuant Data Quality Engine.

Automated data quality validation and monitoring.
Checks:
    - Missing values
    - Duplicate records
    - Outliers (statistical and domain-based)
    - Data freshness / timeliness
    - Invalid values (type, range, enum)
    - Referential integrity

Usage::

    engine = QualityEngine(QualityConfig())
    engine.add_rule("market_tick", NotNullRule(field="price"))
    report = engine.validate("market_tick", data)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from services.data_platform.config import (
    QualityConfig,
    QualityRuleType,
)


# ============================================================================
# Quality Rules
# ============================================================================


@dataclass
class QualityRule(ABC):
    """Abstract base class for quality rules."""

    name: str
    rule_type: QualityRuleType = QualityRuleType.CUSTOM  # Override in subclass __post_init__
    field: Optional[str] = None
    description: str = ""
    severity: str = "error"  # error, warning, info
    enabled: bool = True

    @abstractmethod
    def check(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check data against this rule.

        Args:
            data: List of records to check.

        Returns:
            List of violation dicts with record index and message.
        """
        ...

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "rule_type": self.rule_type.value,
            "field": self.field,
            "description": self.description,
            "severity": self.severity,
            "enabled": self.enabled,
        }


@dataclass
class NotNullRule(QualityRule):
    """Check that a field is not null/empty."""

    def __post_init__(self) -> None:
        self.rule_type = QualityRuleType.NOT_NULL

    def check(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        violations = []
        for i, record in enumerate(data):
            value = record.get(self.field) if self.field else None
            if value is None or value == "":
                violations.append({
                    "record": i,
                    "field": self.field,
                    "rule": self.name,
                    "message": f"Field '{self.field}' is null or empty",
                    "severity": self.severity,
                })
        return violations


@dataclass
class UniqueRule(QualityRule):
    """Check that a field has unique values."""

    def __post_init__(self) -> None:
        self.rule_type = QualityRuleType.UNIQUE

    def check(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        violations = []
        seen: Dict[Any, int] = {}

        for i, record in enumerate(data):
            value = record.get(self.field) if self.field else None
            if value in seen:
                violations.append({
                    "record": i,
                    "field": self.field,
                    "rule": self.name,
                    "message": f"Duplicate value '{value}' for field '{self.field}' "
                               f"(first seen at record {seen[value]})",
                    "severity": self.severity,
                })
            else:
                seen[value] = i

        return violations


@dataclass
class RangeRule(QualityRule):
    """Check that a numeric field is within a range."""

    min_value: Optional[float] = None
    max_value: Optional[float] = None
    inclusive: bool = True

    def __post_init__(self) -> None:
        self.rule_type = QualityRuleType.RANGE

    def check(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        violations = []
        for i, record in enumerate(data):
            value = record.get(self.field) if self.field else None
            if value is None:
                continue

            try:
                num = float(value)
            except (TypeError, ValueError):
                violations.append({
                    "record": i,
                    "field": self.field,
                    "rule": self.name,
                    "message": f"Value '{value}' is not numeric",
                    "severity": self.severity,
                })
                continue

            if self.min_value is not None:
                if self.inclusive and num < self.min_value:
                    violations.append({
                        "record": i,
                        "field": self.field,
                        "rule": self.name,
                        "message": f"Value {num} < min {self.min_value}",
                        "severity": self.severity,
                    })
                elif not self.inclusive and num <= self.min_value:
                    violations.append({
                        "record": i,
                        "field": self.field,
                        "rule": self.name,
                        "message": f"Value {num} <= min {self.min_value}",
                        "severity": self.severity,
                    })

            if self.max_value is not None:
                if self.inclusive and num > self.max_value:
                    violations.append({
                        "record": i,
                        "field": self.field,
                        "rule": self.name,
                        "message": f"Value {num} > max {self.max_value}",
                        "severity": self.severity,
                    })
                elif not self.inclusive and num >= self.max_value:
                    violations.append({
                        "record": i,
                        "field": self.field,
                        "rule": self.name,
                        "message": f"Value {num} >= max {self.max_value}",
                        "severity": self.severity,
                    })

        return violations


@dataclass
class EnumRule(QualityRule):
    """Check that a field value is in an allowed set."""

    allowed_values: List[Any] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.rule_type = QualityRuleType.ENUM

    def check(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        violations = []
        allowed_set = set(self.allowed_values)

        for i, record in enumerate(data):
            value = record.get(self.field) if self.field else None
            if value is not None and value not in allowed_set:
                violations.append({
                    "record": i,
                    "field": self.field,
                    "rule": self.name,
                    "message": f"Value '{value}' not in allowed values: {self.allowed_values}",
                    "severity": self.severity,
                })

        return violations


@dataclass
class RegexRule(QualityRule):
    """Check that a field matches a regex pattern."""

    pattern: str = ""

    def __post_init__(self) -> None:
        self.rule_type = QualityRuleType.REGEX

    def check(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        import re
        violations = []

        try:
            compiled = re.compile(self.pattern)
        except re.error:
            return [{
                "record": -1,
                "field": self.field,
                "rule": self.name,
                "message": f"Invalid regex pattern: {self.pattern}",
                "severity": "error",
            }]

        for i, record in enumerate(data):
            value = record.get(self.field) if self.field else None
            if value is not None and not compiled.match(str(value)):
                violations.append({
                    "record": i,
                    "field": self.field,
                    "rule": self.name,
                    "message": f"Value '{value}' does not match pattern '{self.pattern}'",
                    "severity": self.severity,
                })

        return violations


@dataclass
class CustomRule(QualityRule):
    """Custom quality rule with a user-defined check function."""

    check_fn: Optional[Callable[[Dict[str, Any]], bool]] = None
    message_template: str = "Custom check failed"

    def __post_init__(self) -> None:
        self.rule_type = QualityRuleType.CUSTOM

    def check(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        violations = []

        if not self.check_fn:
            return violations

        for i, record in enumerate(data):
            try:
                if not self.check_fn(record):
                    violations.append({
                        "record": i,
                        "field": self.field,
                        "rule": self.name,
                        "message": self.message_template,
                        "severity": self.severity,
                    })
            except Exception as e:
                violations.append({
                    "record": i,
                    "field": self.field,
                    "rule": self.name,
                    "message": f"Check error: {e}",
                    "severity": self.severity,
                })

        return violations


@dataclass
class TimelinessRule(QualityRule):
    """Check that data is fresh enough."""

    timestamp_field: str = "timestamp"
    max_age_hours: float = 24.0

    def __post_init__(self) -> None:
        self.rule_type = QualityRuleType.TIMELINESS

    def check(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        violations = []
        now = datetime.utcnow()

        for i, record in enumerate(data):
            ts_str = record.get(self.timestamp_field)
            if ts_str is None:
                continue

            try:
                if isinstance(ts_str, datetime):
                    ts = ts_str
                else:
                    ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
                age = (now - ts.replace(tzinfo=None)).total_seconds() / 3600

                if age > self.max_age_hours:
                    violations.append({
                        "record": i,
                        "field": self.timestamp_field,
                        "rule": self.name,
                        "message": f"Data is {age:.1f}h old (max {self.max_age_hours}h)",
                        "severity": self.severity,
                    })
            except (ValueError, TypeError):
                violations.append({
                    "record": i,
                    "field": self.timestamp_field,
                    "rule": self.name,
                    "message": f"Cannot parse timestamp: {ts_str}",
                    "severity": self.severity,
                })

        return violations


# ============================================================================
# Quality Report
# ============================================================================


@dataclass
class QualityReport:
    """Report from a quality validation run."""

    dataset: str
    status: str = "passed"  # passed, warning, failed
    total_records: int = 0
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warning_checks: int = 0
    violations: List[Dict[str, Any]] = field(default_factory=list)
    rule_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0

    @property
    def summary(self) -> str:
        """Get a one-line summary."""
        return (
            f"[{self.status.upper()}] {self.dataset}: "
            f"{self.passed_checks}/{self.total_checks} passed, "
            f"{len(self.violations)} violations"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "status": self.status,
            "total_records": self.total_records,
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "warning_checks": self.warning_checks,
            "violations": self.violations,
            "rule_results": self.rule_results,
            "checked_at": self.checked_at.isoformat(),
            "duration_ms": self.duration_ms,
            "summary": self.summary,
        }


# ============================================================================
# Quality Engine
# ============================================================================


class QualityEngine:
    """Data Quality Engine.

    Manages quality rules, runs validations, and produces reports.

    Usage::

        engine = QualityEngine(QualityConfig())
        engine.add_rule("market_tick", NotNullRule(field="price"))
        engine.add_rule("market_tick", RangeRule(field="volume", min_value=0))
        report = engine.validate("market_tick", data)
        if report.status == "failed":
            print(f"Quality issues: {report.summary}")
    """

    def __init__(self, config: Optional[QualityConfig] = None) -> None:
        self.config = config or QualityConfig()
        self._rules: Dict[str, List[QualityRule]] = {}
        self._history: Dict[str, List[QualityReport]] = {}

    # ------------------------------------------------------------------
    # Rule Management
    # ------------------------------------------------------------------

    def add_rule(self, dataset: str, rule: QualityRule) -> None:
        """Add a quality rule for a dataset.

        Args:
            dataset: Dataset name.
            rule: QualityRule to add.

        Raises:
            ValueError: If max rules exceeded.
        """
        if dataset not in self._rules:
            self._rules[dataset] = []

        if len(self._rules[dataset]) >= self.config.max_rules_per_dataset:
            raise ValueError(
                f"Max rules ({self.config.max_rules_per_dataset}) "
                f"exceeded for dataset '{dataset}'"
            )

        self._rules[dataset].append(rule)

    def remove_rule(self, dataset: str, rule_name: str) -> bool:
        """Remove a quality rule by name.

        Args:
            dataset: Dataset name.
            rule_name: Rule name to remove.

        Returns:
            True if removed.
        """
        if dataset not in self._rules:
            return False

        before = len(self._rules[dataset])
        self._rules[dataset] = [
            r for r in self._rules[dataset] if r.name != rule_name
        ]
        return len(self._rules[dataset]) < before

    def get_rules(self, dataset: str) -> List[QualityRule]:
        """Get all quality rules for a dataset."""
        return self._rules.get(dataset, [])

    def list_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        """List all rules across all datasets."""
        return {
            dataset: [r.to_dict() for r in rules]
            for dataset, rules in self._rules.items()
        }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(
        self,
        dataset: str,
        data: List[Dict[str, Any]],
    ) -> QualityReport:
        """Run all quality rules against a dataset.

        Args:
            dataset: Dataset name.
            data: Data records to validate.

        Returns:
            QualityReport with validation results.
        """
        start = datetime.utcnow()

        rules = self._rules.get(dataset, [])
        enabled_rules = [r for r in rules if r.enabled]

        report = QualityReport(
            dataset=dataset,
            total_records=len(data),
            total_checks=len(enabled_rules),
        )

        for rule in enabled_rules:
            try:
                violations = rule.check(data)
                result = {
                    "passed": len(violations) == 0,
                    "violation_count": len(violations),
                }

                if violations:
                    if rule.severity == "error":
                        report.failed_checks += 1
                        result["status"] = "failed"
                    else:
                        report.warning_checks += 1
                        result["status"] = "warning"

                    report.violations.extend(violations)
                else:
                    report.passed_checks += 1
                    result["status"] = "passed"

                report.rule_results[rule.name] = result

            except Exception as e:
                report.failed_checks += 1
                report.rule_results[rule.name] = {
                    "passed": False,
                    "violation_count": 1,
                    "status": "error",
                    "error": str(e),
                }
                report.violations.append({
                    "rule": rule.name,
                    "message": f"Rule execution error: {e}",
                    "severity": "error",
                })

        # Determine overall status
        if report.failed_checks > 0:
            report.status = "failed"
        elif report.warning_checks > 0:
            report.status = "warning"
        else:
            report.status = "passed"

        report.duration_ms = (datetime.utcnow() - start).total_seconds() * 1000

        # Store in history
        self._history.setdefault(dataset, []).append(report)
        if len(self._history[dataset]) > self.config.store_results_days:
            self._history[dataset] = self._history[dataset][-self.config.store_results_days:]

        return report

    def validate_record(self, dataset: str, record: Dict[str, Any]) -> QualityReport:
        """Validate a single record.

        Args:
            dataset: Dataset name.
            record: Single data record.

        Returns:
            QualityReport.
        """
        return self.validate(dataset, [record])

    # ------------------------------------------------------------------
    # Quick Checks
    # ------------------------------------------------------------------

    def check_missing(
        self, data: List[Dict[str, Any]], field: str
    ) -> Tuple[int, float]:
        """Check missing rate for a field.

        Returns:
            (missing_count, missing_rate).
        """
        total = len(data)
        if total == 0:
            return 0, 0.0

        missing = sum(
            1 for r in data
            if field not in r or r[field] is None or r[field] == ""
        )
        return missing, missing / total

    def check_duplicates(
        self, data: List[Dict[str, Any]], fields: Optional[List[str]] = None
    ) -> Tuple[int, float]:
        """Check duplicate rate.

        Args:
            data: Data records.
            fields: Fields to check for duplicates (all if None).

        Returns:
            (duplicate_count, duplicate_rate).
        """
        total = len(data)
        if total == 0:
            return 0, 0.0

        if fields:
            keys = [tuple(r.get(f) for f in fields) for r in data]
        else:
            keys = [tuple(sorted(r.items())) for r in data]

        unique = len(set(keys))
        duplicates = total - unique
        return duplicates, duplicates / total

    def check_outliers_iqr(
        self, data: List[Dict[str, Any]], field: str, multiplier: float = 1.5
    ) -> List[Dict[str, Any]]:
        """Detect outliers using IQR method.

        Args:
            data: Data records.
            field: Numeric field to check.
            multiplier: IQR multiplier (default 1.5).

        Returns:
            List of outlier records.
        """
        values = []
        for r in data:
            v = r.get(field)
            if v is not None:
                try:
                    values.append(float(v))
                except (TypeError, ValueError):
                    pass

        if len(values) < 4:
            return []

        values.sort()
        n = len(values)
        q1 = values[n // 4]
        q3 = values[3 * n // 4]
        iqr = q3 - q1

        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr

        outliers = []
        for r in data:
            v = r.get(field)
            if v is not None:
                try:
                    fv = float(v)
                    if fv < lower or fv > upper:
                        outliers.append({**r, "_outlier_reason": f"Value {fv} outside [{lower:.2f}, {upper:.2f}]"})
                except (TypeError, ValueError):
                    pass

        return outliers

    # ------------------------------------------------------------------
    # History & Stats
    # ------------------------------------------------------------------

    def get_history(self, dataset: str) -> List[QualityReport]:
        """Get validation history for a dataset."""
        return self._history.get(dataset, [])

    def get_latest_report(self, dataset: str) -> Optional[QualityReport]:
        """Get the most recent quality report for a dataset."""
        history = self._history.get(dataset, [])
        return history[-1] if history else None

    def get_quality_score(self, dataset: str) -> float:
        """Get a quality score (0-100) for a dataset.

        Based on recent validation history.
        """
        history = self._history.get(dataset, [])
        if not history:
            return 100.0

        recent = history[-10:]  # Last 10 validations
        scores = []
        for report in recent:
            if report.total_checks > 0:
                score = (report.passed_checks / report.total_checks) * 100
            else:
                score = 100.0
            scores.append(score)

        return sum(scores) / len(scores)

    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall quality statistics across all datasets."""
        dataset_scores: Dict[str, float] = {}
        total_rules = sum(len(rules) for rules in self._rules.values())
        total_datasets = len(self._rules)

        for dataset in self._rules:
            dataset_scores[dataset] = self.get_quality_score(dataset)

        avg_score = (
            sum(dataset_scores.values()) / len(dataset_scores)
            if dataset_scores else 100.0
        )

        return {
            "datasets_monitored": total_datasets,
            "total_rules": total_rules,
            "average_quality_score": round(avg_score, 2),
            "dataset_scores": dataset_scores,
            "total_validations": sum(
                len(history) for history in self._history.values()
            ),
        }
