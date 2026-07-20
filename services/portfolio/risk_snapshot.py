"""
Risk snapshot.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RiskSnapshot:
    strategy_id: str
    allocated_risk: Decimal
    remaining_risk: Decimal