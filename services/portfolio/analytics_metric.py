"""
Portfolio analytics metric model.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AnalyticsMetric:
    name: str
    value: Decimal
    category: str