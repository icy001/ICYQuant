"""
Strategy portfolio model.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class StrategyPortfolio:
    strategy_id: str
    allocated_capital: Decimal
    current_value: Decimal