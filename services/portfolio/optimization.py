"""
Portfolio optimization model.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class OptimizationResult:
    weights: dict[str, Decimal]
    expected_return: Decimal
    expected_risk: Decimal