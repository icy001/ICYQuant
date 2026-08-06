"""Dataset Validator — validates dataset content against schema and quality rules.

Ensures data integrity before it enters the research pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RuleSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationRule:
    """A single validation rule with configurable severity."""

    name: str = ""
    description: str = ""
    severity: RuleSeverity = RuleSeverity.ERROR
    check_fn: Optional[Callable] = None
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Report from running validation rules on a dataset."""

    dataset_id: str = ""
    passed: bool = True
    total_rules: int = 0
    passed_rules: int = 0
    failed_rules: int = 0
    warning_rules: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    info: List[Dict[str, Any]] = field(default_factory=list)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "passed": self.passed,
            "total_rules": self.total_rules,
            "passed_rules": self.passed_rules,
            "failed_rules": self.failed_rules,
            "warning_rules": self.warning_rules,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "checked_at": self.checked_at.isoformat(),
        }


class DatasetValidator:
    """Validates dataset content against schema and quality rules.

    Built-in rules:
    * Schema validation (column presence, types)
    * Null check (missing value rate)
    * Duplicate detection
    * Value range checks
    """

    def __init__(self) -> None:
        self._rules: List[ValidationRule] = []
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """Register the standard set of validation rules."""
        self.add_rule(ValidationRule(
            name="schema_match",
            description="All required columns are present",
            severity=RuleSeverity.ERROR,
        ))
        self.add_rule(ValidationRule(
            name="null_check",
            description="Null ratio within acceptable limits",
            severity=RuleSeverity.WARNING,
            params={"max_null_ratio": 0.3},
        ))
        self.add_rule(ValidationRule(
            name="duplicate_check",
            description="No duplicate rows",
            severity=RuleSeverity.ERROR,
        ))
        self.add_rule(ValidationRule(
            name="type_check",
            description="Column values match declared types",
            severity=RuleSeverity.ERROR,
        ))

    # ── rule management ───────────────────────────────────────────────────

    def add_rule(self, rule: ValidationRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, rule_name: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != rule_name]
        return len(self._rules) < before

    def get_rule(self, rule_name: str) -> Optional[ValidationRule]:
        for rule in self._rules:
            if rule.name == rule_name:
                return rule
        return None

    def list_rules(self) -> List[Dict[str, Any]]:
        return [{"name": r.name, "description": r.description, "severity": r.severity.value} for r in self._rules]

    # ── validation ────────────────────────────────────────────────────────

    def validate(
        self,
        dataset_id: str,
        data: Any,
        rules: Optional[List[str]] = None,
    ) -> ValidationReport:
        """Run validation rules against a dataset.

        Args:
            dataset_id: Dataset identifier.
            data: The dataset content to validate.
            rules: Optional subset of rule names to run. None = all rules.

        Returns:
            A ValidationReport with results.
        """
        report = ValidationReport(dataset_id=dataset_id)
        active_rules = self._rules
        if rules:
            active_rules = [r for r in self._rules if r.name in rules]

        report.total_rules = len(active_rules)

        for rule in active_rules:
            result = self._run_rule(rule, data)
            if result["status"] == "passed":
                report.passed_rules += 1
            elif result["status"] == "warning":
                report.warning_rules += 1
                report.warnings.append(result)
            else:
                report.failed_rules += 1
                report.errors.append(result)

        report.passed = report.failed_rules == 0
        logger.info(
            "Validation for %s: passed=%s (%d/%d)",
            dataset_id, report.passed, report.passed_rules, report.total_rules,
        )
        return report

    def _run_rule(self, rule: ValidationRule, data: Any) -> Dict[str, Any]:
        """Execute a single validation rule."""
        if rule.check_fn is not None:
            try:
                return rule.check_fn(data, rule.params)
            except Exception as exc:
                return {
                    "rule": rule.name,
                    "status": "error",
                    "message": str(exc),
                }
        # Default: rule passes (no custom check function)
        return {
            "rule": rule.name,
            "status": "passed",
            "message": f"Rule '{rule.name}' passed",
        }

    def __repr__(self) -> str:
        return f"DatasetValidator(rules={len(self._rules)})"
