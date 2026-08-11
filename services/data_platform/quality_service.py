"""
ICYQuant Data Quality Service.

Commit 16 Part 1.5 — Unified data quality management service.
Provides quality rule definition, automated quality checks, quality
scoring, and alerting across all datasets in the data platform.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class QualityRuleType(str, Enum):
    """Types of quality rules."""
    NOT_NULL = "not_null"
    UNIQUE = "unique"
    RANGE = "range"
    ENUM = "enum"
    REGEX = "regex"
    REFERENTIAL = "referential"
    CUSTOM = "custom"
    FRESHNESS = "freshness"
    COMPLETENESS = "completeness"


class QualitySeverity(str, Enum):
    """Severity level for quality violations."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class QualityRule:
    """A data quality rule definition."""
    rule_id: str = ""
    dataset_id: str = ""
    rule_type: QualityRuleType = QualityRuleType.NOT_NULL
    column: str = ""
    description: str = ""
    severity: QualitySeverity = QualitySeverity.WARNING
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)
    check_fn: Optional[Callable] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityViolation:
    """A quality rule violation."""
    violation_id: str = ""
    rule_id: str = ""
    dataset_id: str = ""
    column: str = ""
    severity: QualitySeverity = QualitySeverity.WARNING
    message: str = ""
    value: Any = None
    expected: Any = None
    row_index: int = -1
    timestamp: Optional[datetime] = None


@dataclass
class QualityReport:
    """Aggregated quality report for a dataset."""
    dataset_id: str = ""
    overall_score: float = 100.0
    rules_checked: int = 0
    rules_passed: int = 0
    rules_failed: int = 0
    violations: list[QualityViolation] = field(default_factory=list)
    checked_at: Optional[datetime] = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class QualityService:
    """Unified data quality management service.

    Provides:
      - Quality rule definition and management
      - Automated quality checks against datasets
      - Quality scoring (0-100)
      - Trend analysis and alerting
      - Quality dashboards and reporting
    """

    def __init__(self) -> None:
        self._rules: dict[str, QualityRule] = {}
        self._reports: dict[str, list[QualityReport]] = {}
        self._violation_counter = 0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Rule Management
    # ------------------------------------------------------------------

    async def add_rule(self, rule: QualityRule) -> str:
        """Add a quality rule."""
        async with self._lock:
            self._rules[rule.rule_id] = rule
        logger.info("Quality rule added: %s (%s.%s)", rule.rule_id, rule.dataset_id, rule.column)
        return rule.rule_id

    async def get_rule(self, rule_id: str) -> Optional[QualityRule]:
        """Get a quality rule by ID."""
        return self._rules.get(rule_id)

    async def list_rules(self, dataset_id: Optional[str] = None) -> list[QualityRule]:
        """List quality rules with optional dataset filter."""
        rules = list(self._rules.values())
        if dataset_id:
            rules = [r for r in rules if r.dataset_id == dataset_id]
        return rules

    async def remove_rule(self, rule_id: str) -> bool:
        """Remove a quality rule."""
        async with self._lock:
            return self._rules.pop(rule_id, None) is not None

    async def enable_rule(self, rule_id: str) -> bool:
        """Enable a quality rule."""
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = True
            return True
        return False

    async def disable_rule(self, rule_id: str) -> bool:
        """Disable a quality rule."""
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = False
            return True
        return False

    # ------------------------------------------------------------------
    # Quality Checks
    # ------------------------------------------------------------------

    async def check_dataset(self, dataset_id: str, data: list[dict[str, Any]]) -> QualityReport:
        """Run all quality rules against a dataset."""
        start = datetime.now(timezone.utc)
        report = QualityReport(dataset_id=dataset_id, checked_at=start)

        rules = await self.list_rules(dataset_id)
        rules = [r for r in rules if r.enabled]
        report.rules_checked = len(rules)

        for rule in rules:
            violations = self._check_rule(rule, data)
            if violations:
                report.rules_failed += 1
                report.violations.extend(violations)
            else:
                report.rules_passed += 1

        # Compute score
        if report.rules_checked > 0:
            report.overall_score = (report.rules_passed / report.rules_checked) * 100.0

        report.duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        # Store report
        if dataset_id not in self._reports:
            self._reports[dataset_id] = []
        self._reports[dataset_id].append(report)

        return report

    def _check_rule(self, rule: QualityRule, data: list[dict[str, Any]]) -> list[QualityViolation]:
        """Execute a single quality rule against data."""
        violations: list[QualityViolation] = []

        for i, row in enumerate(data):
            value = row.get(rule.column)

            if rule.rule_type == QualityRuleType.NOT_NULL:
                if value is None or value == "":
                    violations.append(self._make_violation(rule, i, value, "not null"))

            elif rule.rule_type == QualityRuleType.RANGE:
                min_val = rule.params.get("min")
                max_val = rule.params.get("max")
                if value is not None:
                    try:
                        fv = float(value)
                        if min_val is not None and fv < min_val:
                            violations.append(self._make_violation(rule, i, value, f">= {min_val}"))
                        if max_val is not None and fv > max_val:
                            violations.append(self._make_violation(rule, i, value, f"<= {max_val}"))
                    except (ValueError, TypeError):
                        violations.append(self._make_violation(rule, i, value, "numeric"))

            elif rule.rule_type == QualityRuleType.ENUM:
                allowed = set(rule.params.get("values", []))
                if value is not None and str(value) not in allowed:
                    violations.append(self._make_violation(rule, i, value, str(allowed)))

            elif rule.rule_type == QualityRuleType.REGEX:
                import re
                pattern = rule.params.get("pattern", "")
                if value is not None and pattern and not re.match(pattern, str(value)):
                    violations.append(self._make_violation(rule, i, value, f"matching {pattern}"))

        return violations

    def _make_violation(self, rule: QualityRule, row_idx: int, value: Any, expected: Any) -> QualityViolation:
        self._violation_counter += 1
        return QualityViolation(
            violation_id=f"qv-{self._violation_counter:08d}",
            rule_id=rule.rule_id,
            dataset_id=rule.dataset_id,
            column=rule.column,
            severity=rule.severity,
            message=f"{rule.description or rule.rule_type.value} check failed",
            value=value,
            expected=expected,
            row_index=row_idx,
            timestamp=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    async def get_latest_report(self, dataset_id: str) -> Optional[QualityReport]:
        """Get the most recent quality report."""
        reports = self._reports.get(dataset_id, [])
        return reports[-1] if reports else None

    async def get_report_history(self, dataset_id: str, limit: int = 100) -> list[QualityReport]:
        """Get quality report history for a dataset."""
        reports = self._reports.get(dataset_id, [])
        return reports[-limit:]

    async def get_trend(self, dataset_id: str, window: int = 50) -> list[float]:
        """Get quality score trend for a dataset."""
        reports = self._reports.get(dataset_id, [])[-window:]
        return [r.overall_score for r in reports]

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    @property
    def report_count(self) -> int:
        return sum(len(r) for r in self._reports.values())
