"""
Risk budget model.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class RiskBudget:
    strategy_id: str
    max_risk: Decimal
    used_risk: Decimal