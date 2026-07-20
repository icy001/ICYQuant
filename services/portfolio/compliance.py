"""
Portfolio compliance models.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ComplianceRule:
    rule_id: str
    rule_name: str
    limit_value: Decimal


@dataclass(frozen=True)
class ComplianceViolation:
    rule_id: str
    message: str
    actual_value: Decimal
    limit_value: Decimal