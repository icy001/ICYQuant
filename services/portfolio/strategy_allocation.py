"""
Strategy allocation model.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class StrategyAllocation:
    strategy_id: str
    weight: Decimal