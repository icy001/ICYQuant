"""Rule Validation Engine – validates AI output against risk, position, compliance rules."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ValidationStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


@dataclass
class ValidationResult:
    status: ValidationStatus
    rule_name: str
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class RuleValidationEngine:
    """Validates AI decisions against institutional rules."""

    def __init__(self) -> None:
        self._rules: List[Dict[str, Any]] = []
        self._results: List[ValidationResult] = []

    def validate(self, risk_ok: bool, position_ok: bool) -> bool:
        """Basic validation: both risk and position checks must pass."""
        return risk_ok and position_ok

    def validate_all(self, checks: Dict[str, bool]) -> ValidationResult:
        """Run multiple named checks and aggregate.

        Args:
            checks: {"risk_check": True, "position_check": False, ...}.

        Returns:
            Aggregated ValidationResult.
        """
        if not checks:
            return ValidationResult(
                status=ValidationStatus.PASS,
                rule_name="no_rules",
                message="No rules to validate",
            )

        all_pass = all(checks.values())
        failures = [name for name, ok in checks.items() if not ok]

        if all_pass:
            return ValidationResult(
                status=ValidationStatus.PASS,
                rule_name="all_checks",
                message=f"All {len(checks)} checks passed",
                details={"passed": len(checks)},
            )

        return ValidationResult(
            status=ValidationStatus.FAIL,
            rule_name="multi_check",
            message=f"Failed checks: {', '.join(failures)}",
            details={"passed": len(checks) - len(failures), "failed": len(failures), "failures": failures},
        )

    def add_rule(self, name: str, description: str, enabled: bool = True) -> None:
        self._rules.append({"name": name, "description": description, "enabled": enabled})

    def check_rule(self, name: str, condition: bool, message: str = "") -> ValidationResult:
        status = ValidationStatus.PASS if condition else ValidationStatus.FAIL
        result = ValidationResult(status=status, rule_name=name, message=message)
        self._results.append(result)
        return result

    def summary(self) -> Dict[str, Any]:
        passed = sum(1 for r in self._results if r.status == ValidationStatus.PASS)
        failed = sum(1 for r in self._results if r.status == ValidationStatus.FAIL)
        return {"total": len(self._results), "passed": passed, "failed": failed, "all_pass": failed == 0}
