"""
Compliance breach detector.
"""

from .compliance import ComplianceViolation


class BreachDetector:
    def detect(
        self,
        rule,
        actual_value,
    ):
        if actual_value > rule.limit_value:
            return ComplianceViolation(
                rule_id=rule.rule_id,
                message="limit breached",
                actual_value=actual_value,
                limit_value=rule.limit_value,
            )
        return None